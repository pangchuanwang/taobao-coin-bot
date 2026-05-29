from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from utils import TB_APP, ALIPAY_APP, FISH_APP, get_current_app, start_app


TaskHandler = Callable[[dict[str, Any], "TaskHandlerContext"], None]
TASK_HANDLERS: dict[str, TaskHandler] = {}


@dataclass(frozen=True)
class TaskHandlerContext:
    device: Any
    back_to_task: Callable[[], None]
    task_loop: Callable[..., None]


def register_task_handler(name: str):
    def decorator(func: TaskHandler) -> TaskHandler:
        TASK_HANDLERS[name] = func
        return func

    return decorator


def has_task_handler(name: str) -> bool:
    return name in TASK_HANDLERS


def get_task_handler(name: str) -> TaskHandler:
    return TASK_HANDLERS[name]


@register_task_handler("browse")
def browse_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    ctx.task_loop(ctx.device, ctx.back_to_task, duration=task["effective_seconds"])


@register_task_handler("browse_only")
def browse_only_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    ctx.task_loop(ctx.device, ctx.back_to_task, duration=task["effective_seconds"])


@register_task_handler("claim")
def claim_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    ctx.task_loop(ctx.device, ctx.back_to_task, duration=task["effective_seconds"])


@register_task_handler("quiz")
def quiz_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    d = ctx.device
    effective_seconds = task["effective_seconds"]

    # ── Phase 1: detect quiz page ──
    quiz_detected = _quiz_wait_for_page(d, timeout=8)
    if not quiz_detected:
        print("[quiz] 未检测到答题页，回退到通用浏览")
        ctx.task_loop(d, ctx.back_to_task, duration=effective_seconds)
        return

    # ── Phase 2: find answer options ──
    options = _quiz_find_options(d)
    if not options:
        print("[quiz] 未找到可选答案，等待后重试")
        time.sleep(3)
        options = _quiz_find_options(d)

    # ── Phase 3: click an answer ──
    if options:
        _quiz_click_answer(d, options)
    else:
        print("[quiz] 仍无可用答案，跳过答题")

    # ── Phase 4: claim reward ──
    _quiz_claim_reward(d)

    # ── Phase 5: return ──
    ctx.back_to_task()


# ── quiz helper functions ──

_QUIZ_PAGE_INDICATORS = ["题", "课堂", "答题", "趣味", "选择", "答案"]
_QUIZ_OPTION_TEXT_PATTERNS = ["A.", "B.", "C.", "D.", "A、", "B、", "C、", "D、",
                              "选项一", "选项二", "选项三", "选项四",
                              "①", "②", "③", "④"]
_REWARD_BUTTON_TEXTS = ["领取奖励", "领取", "知道了", "继续答题", "下一题", "完成"]


def _quiz_wait_for_page(d, timeout: float = 8) -> bool:
    """Wait until the quiz page is visible. Returns True if detected."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            for indicator in _QUIZ_PAGE_INDICATORS:
                el = d(textContains=indicator)
                if el.exists:
                    print(f"[quiz] 检测到答题页标志: \"{indicator}\"")
                    time.sleep(1)
                    return True
            # Also check for a WebView that might host the quiz
            wv = d(className="android.webkit.WebView")
            if wv.exists:
                print("[quiz] 检测到 WebView 容器，视为答题页")
                time.sleep(1)
                return True
        except Exception as e:
            print(f"[quiz] 检测答题页异常: {e}")
        time.sleep(1)
    return False


def _quiz_find_options(d) -> list:
    """Try to locate answer option elements. Returns list of (element, label) tuples."""
    options = []

    # Strategy 1: look for text matching option patterns (A./B./①/② etc.)
    for pattern in _QUIZ_OPTION_TEXT_PATTERNS:
        prefix = pattern.rstrip(".、")
        # Search for text starting with the pattern
        try:
            el = d(textStartsWith=prefix)
            if el.exists:
                count = el.count
                for i in range(min(count, 4)):
                    item = el[i]
                    label = item.get_text() or f"option_{i}"
                    options.append((item, label))
                    print(f"[quiz] 发现选项: \"{label}\"")
                if options:
                    return options
        except Exception:
            pass

    # Strategy 2: look for clickable TextViews inside a common parent container
    # Typical quiz layout: a group of equally-sized clickable cards
    try:
        clickable_tvs = d(className="android.widget.TextView", clickable=True)
        if clickable_tvs.count >= 2:
            count = min(clickable_tvs.count, 6)
            for i in range(count):
                item = clickable_tvs[i]
                label = item.get_text() or f"clickable_{i}"
                # Skip elements that look like navigation/controls
                if any(skip in label for skip in ["返回", "关闭", "分享", "更多"]):
                    continue
                options.append((item, label))
                print(f"[quiz] 发现可点击文本: \"{label}\"")
            if len(options) >= 2:
                return options
    except Exception as e:
        print(f"[quiz] 策略2异常: {e}")

    # Strategy 3: look for Button elements that could be answers
    try:
        buttons = d(className="android.widget.Button")
        if buttons.count >= 2:
            count = min(buttons.count, 6)
            for i in range(count):
                item = buttons[i]
                label = item.get_text() or f"btn_{i}"
                if any(skip in label for skip in ["返回", "关闭", "分享", "更多", "去完成"]):
                    continue
                options.append((item, label))
                print(f"[quiz] 发现按钮选项: \"{label}\"")
            if len(options) >= 2:
                return options
    except Exception as e:
        print(f"[quiz] 策略3异常: {e}")

    print("[quiz] 所有策略均未找到答案选项")
    return []


def _quiz_click_answer(d, options: list) -> None:
    """Click one answer from the options list. Strategy: pick the first one."""
    if not options:
        return
    element, label = options[0]
    try:
        print(f"[quiz] 选择答案: \"{label}\"")
        element.click()
        time.sleep(2)
    except Exception as e:
        print(f"[quiz] 点击答案异常: {e}")


def _quiz_claim_reward(d) -> None:
    """Look for a reward claim button and click it."""
    for text in _REWARD_BUTTON_TEXTS:
        try:
            btn = d(textContains=text)
            if btn.exists:
                print(f"[quiz] 点击领取: \"{text}\"")
                btn.click()
                time.sleep(2)
                return
        except Exception as e:
            print(f"[quiz] 领取异常({text}): {e}")
    print("[quiz] 未发现领取按钮")


@register_task_handler("game")
def game_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    ctx.task_loop(ctx.device, ctx.back_to_task, duration=task["effective_seconds"])


# ── cross-app navigation helper ──

_CROSS_APP_TIMEOUT = 45


def _detect_return_state(d) -> str:
    """检测当前返回状态，返回三个值之一：
    'external'  - 仍在外部 App（支付宝/闲鱼/其他非淘宝）
    'taobao'    - 已回到淘宝但不在淘金币任务页
    'task_list' - 已回到淘金币任务页
    """
    try:
        pkg, _ = get_current_app(d)
        if pkg is None:
            return "external"
        if TB_APP not in pkg:
            return "external"
        # 在淘宝内，检查是否是任务列表
        coin_view = d(className="android.webkit.WebView", text="淘金币首页")
        if coin_view.exists:
            earn = d(textContains="赚金币抵钱")
            reward = d(textContains="今日累计奖励")
            if earn.exists or reward.exists:
                return "task_list"
        return "taobao"
    except Exception:
        return "external"


def cross_app_navigate_back(d, back_to_task) -> None:
    """从跨 App 任务返回淘金币任务页。

    三阶段恢复策略：
      阶段 1（0-15s）：原路返回 —— 在外部 App 中按 back，或拉回淘宝后逐级 back
      阶段 2（15-35s）：重启淘宝 —— start_app 重新拉起淘宝，再 back 到任务页
      阶段 3（35-45s）：兜底 —— 调用 back_to_task() 让主流程处理

    每个阶段都明确区分三个状态：external / taobao / task_list。
    """
    print("[cross-app] 开始返回任务页")
    deadline = time.monotonic() + _CROSS_APP_TIMEOUT
    phase = 1
    phase2_start = deadline - 30  # 15s 后进入阶段 2
    phase3_start = deadline - 10  # 35s 后进入阶段 3

    while time.monotonic() < deadline:
        try:
            state = _detect_return_state(d)
            now = time.monotonic()

            # 已到达任务列表 → 成功
            if state == "task_list":
                print("[cross-app] 已返回任务列表")
                return

            # 判断当前阶段
            if now >= phase3_start:
                if phase != 3:
                    print("[cross-app] 进入阶段3：兜底 back_to_task")
                    phase = 3
                back_to_task()
                return

            if now >= phase2_start and phase < 2:
                print("[cross-app] 进入阶段2：重启淘宝")
                phase = 2

            # 阶段 1：原路返回
            if phase == 1:
                if state == "external":
                    print("[cross-app] 仍在外部 App，尝试拉回淘宝")
                    start_app(d, TB_APP)
                    time.sleep(3)
                else:
                    # state == "taobao"：在淘宝但不在任务页
                    print("[cross-app] 在淘宝内，逐级 back")
                    d.press("back")
                    time.sleep(1.5)

            # 阶段 2：重启淘宝
            elif phase == 2:
                if state == "external":
                    print("[cross-app] 阶段2：重新启动淘宝")
                    start_app(d, TB_APP, init=True)
                    time.sleep(5)
                else:
                    # state == "taobao"：在淘宝但不在任务页，继续 back
                    print("[cross-app] 阶段2：淘宝内 back")
                    d.press("back")
                    time.sleep(1.5)

        except Exception as e:
            print(f"[cross-app] 返回异常: {e}")
            time.sleep(2)

    # 超时 → 最后一次尝试
    print("[cross-app] 超时，最后调用 back_to_task")
    try:
        back_to_task()
    except Exception as e:
        print(f"[cross-app] 兜底也失败: {e}")


# ── dedicated browse handlers ──

@register_task_handler("search_browse")
def search_browse_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    """领红包搜心仪商品可用 — 等待搜索结果页，滚动浏览，返回。"""
    d = ctx.device
    duration = task["effective_seconds"]
    print(f"[search_browse] 开始，目标浏览 {duration}s")

    # Phase 1: 等待搜索结果页
    if not _wait_for_any_text(d, ["搜索", "筛选", "综合", "销量"], timeout=8):
        print("[search_browse] 未检测到搜索结果页，回退通用浏览")
        ctx.task_loop(d, ctx.back_to_task, duration=duration)
        return

    # Phase 2: 滚动浏览
    _timed_scroll(d, duration, tag="[search_browse]")

    # Phase 3: 返回
    ctx.back_to_task()


@register_task_handler("deep_browse")
def deep_browse_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    """好物沉浸看 — 等待商品详情页，停留浏览，返回。"""
    d = ctx.device
    duration = task["effective_seconds"]
    print(f"[deep_browse] 开始，目标浏览 {duration}s")

    # Phase 1: 等待详情页
    if not _wait_for_any_text(d, ["加入购物车", "立即购买", "¥", "价格"], timeout=8):
        print("[deep_browse] 未检测到商品详情页，回退通用浏览")
        ctx.task_loop(d, ctx.back_to_task, duration=duration)
        return

    # Phase 2: 缓慢滑动浏览
    _timed_scroll(d, duration, tag="[deep_browse]", scroll_speed="slow")

    # Phase 3: 返回
    ctx.back_to_task()


@register_task_handler("event_browse")
def event_browse_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    """来淘宝闪购分百亿补贴 — 等待活动页，浏览但不点击下单，返回。"""
    d = ctx.device
    duration = task["effective_seconds"]
    print(f"[event_browse] 开始，目标浏览 {duration}s")

    # Phase 1: 等待活动页
    if not _wait_for_any_text(d, ["闪购", "补贴", "百亿", "活动"], timeout=8):
        print("[event_browse] 未检测到活动页，回退通用浏览")
        ctx.task_loop(d, ctx.back_to_task, duration=duration)
        return

    # Phase 2: 浏览（仅滑动，不点击任何按钮）
    _timed_scroll(d, duration, tag="[event_browse]")

    # Phase 3: 返回
    ctx.back_to_task()


@register_task_handler("cross_app_claim")
def cross_app_claim_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    """去蚂蚁庄园捐爱心蛋 — 跳支付宝，捐蛋，返回。"""
    d = ctx.device
    print("[cross_app_claim] 开始")

    # Phase 1: 等待跳转到支付宝
    if not _wait_for_package(d, ALIPAY_APP, timeout=10):
        print("[cross_app_claim] 未跳转到支付宝，尝试通用浏览")
        ctx.task_loop(d, ctx.back_to_task, duration=task["effective_seconds"])
        return

    # Phase 2: 等待蚂蚁庄园页面加载
    time.sleep(3)
    _wait_for_any_text(d, ["蚂蚁庄园", "庄园", "爱心蛋", "捐蛋"], timeout=8)

    # Phase 3: 点击捐蛋按钮
    for btn_text in ["捐蛋", "爱心捐", "去捐蛋", "捐爱心蛋", "领取"]:
        try:
            btn = d(textContains=btn_text)
            if btn.exists:
                print(f"[cross_app_claim] 点击: \"{btn_text}\"")
                btn.click()
                time.sleep(3)
                break
        except Exception as e:
            print(f"[cross_app_claim] 点击异常({btn_text}): {e}")

    # Phase 4: 处理确认弹窗
    for confirm_text in ["确认", "确定", "同意", "知道了"]:
        try:
            btn = d(textContains=confirm_text)
            if btn.exists:
                print(f"[cross_app_claim] 确认: \"{confirm_text}\"")
                btn.click()
                time.sleep(2)
                break
        except Exception:
            pass

    # Phase 5: 返回
    cross_app_navigate_back(d, ctx.back_to_task)


@register_task_handler("cross_app_browse")
def cross_app_browse_handler(task: dict[str, Any], ctx: TaskHandlerContext) -> None:
    """去闲鱼币领现金红包 — 跳闲鱼，领取，返回。"""
    d = ctx.device
    print("[cross_app_browse] 开始")

    # Phase 1: 等待跳转到闲鱼
    if not _wait_for_package(d, FISH_APP, timeout=10):
        print("[cross_app_browse] 未跳转到闲鱼，尝试通用浏览")
        ctx.task_loop(d, ctx.back_to_task, duration=task["effective_seconds"])
        return

    # Phase 2: 等待闲鱼币页面
    time.sleep(3)
    _wait_for_any_text(d, ["闲鱼币", "领现金", "红包", "签到"], timeout=8)

    # Phase 3: 点击领取
    for btn_text in ["领取", "签到", "立即领取", "去领取", "收下"]:
        try:
            btn = d(textContains=btn_text)
            if btn.exists:
                print(f"[cross_app_browse] 点击: \"{btn_text}\"")
                btn.click()
                time.sleep(3)
                break
        except Exception as e:
            print(f"[cross_app_browse] 点击异常({btn_text}): {e}")

    # Phase 4: 浏览片刻
    _timed_scroll(d, 5, tag="[cross_app_browse]")

    # Phase 5: 返回
    cross_app_navigate_back(d, ctx.back_to_task)


# ── shared helper functions ──

def _wait_for_any_text(d, texts: list[str], timeout: float = 8) -> bool:
    """等待页面出现任意一个指定文本。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for text in texts:
            try:
                el = d(textContains=text)
                if el.exists:
                    print(f"[handler] 检测到: \"{text}\"")
                    return True
            except Exception:
                pass
        time.sleep(1)
    return False


def _wait_for_package(d, target_package: str, timeout: float = 10) -> bool:
    """等待前台 App 切换到目标 package。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            pkg, _ = get_current_app(d)
            if pkg and target_package in pkg:
                print(f"[handler] 已切换到 {target_package}")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _timed_scroll(d, duration: float, tag: str = "", scroll_speed: str = "normal") -> None:
    """在指定时间内随机滑动页面。"""
    screen_w, screen_h = d.window_size()
    start = time.monotonic()
    interval = 2.0 if scroll_speed == "slow" else 1.2
    while time.monotonic() - start < duration:
        try:
            sx = screen_w // 3
            sy = int(screen_h * 0.7)
            ey = int(screen_h * 0.3)
            d.swipe(sx, sy, sx, ey, duration=0.5)
            print(f"{tag} 滑动")
        except Exception as e:
            print(f"{tag} 滑动异常: {e}")
        time.sleep(interval)
