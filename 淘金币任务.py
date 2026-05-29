import time
from datetime import datetime
from pathlib import Path

import uiautomator2 as u2
from utils import (
    TB_APP,
    check_verify,
    classify_coin_task,
    get_current_app,
    select_device,
    start_app,
    task_loop,
)
from coin_task_planner import (
    RunTracker,
    build_task_record,
    is_first_scan_today,
    prioritize_tasks,
    record_task_outcome,
    refresh_catalog,
)
from coin_task_handlers import (
    TaskHandlerContext,
    get_task_handler,
    has_task_handler,
)

unclick_btn = []
have_clicked = dict()
reviewed_tasks = set()
miss_count = 0
consecutive_errors = 0
time1 = time.time()
RETURN_TIMEOUT = 45
MAX_CONSECUTIVE_ERRORS = 3
MAX_MISS_COUNT = 4
MAX_SCAN_SCROLLS = 6
HIGH_PRIORITY_MIN_SCORE = 2.0
TASK_BUTTON_PATTERN = "去完成|去逛逛|去浏览|逛一逛|立即领|去领取|去看看|搜一下|玩一把|捐一笔|逛一下|爱心捐"
priority_plan = []
planned_once = False
high_priority_rescan_done = False
LOG_DIR = Path(__file__).resolve().parent / "logs"
run_tracker = RunTracker()
selected_device = select_device()
d = u2.connect(selected_device)
print(f"已成功连接设备：{selected_device}")
start_app(d, TB_APP, init=True)
ctx = d.watch_context()
ctx.when("O1CN012qVB9n1tvZ8ATEQGu_!!6000000005964-2-tps-144-144").click()
ctx.when("O1CN01sORayC1hBVsDQRZoO_!!6000000004239-2-tps-426-128.png_").click()
ctx.when("领取今日奖励").click()
ctx.when("确认").click()
ctx.when("确定").click()
ctx.when("刷新").click()
ctx.when("点击刷新").click()
ctx.when(xpath="//android.app.Dialog//android.widget.Button[contains(text(), '-tps-')]").click()
ctx.when(xpath="//android.app.Dialog//android.widget.Button[@text='关闭']").click()
ctx.when(xpath="//android.widget.FrameLayout[@resource-id='com.taobao.taobao:id/poplayer_native_state_center_layout_frame_id']//android.widget.ImageView[@content-desc='关闭按钮']").click()
# ctx.when(xpath="//android.widget.TextView[@package='com.eg.android.AlipayGphone']").click()
ctx.start()
time.sleep(3)


def check_in_task():
    package_name, activity_name = get_current_app(d)
    if package_name == "com.taobao.taobao" and "com.taobao.themis.container.app.TMSActivity" in (activity_name or ""):
        coin_view = d(className="android.webkit.WebView", text="淘金币首页")
        if coin_view.exists:
            earn_btn1 = d(className="android.widget.TextView", text="赚金币抵钱")
            earn_btn2 = d(className="android.widget.TextView", text="今日累计奖励")
            if earn_btn1.exists or earn_btn2.exists:
                return True
            else:
                earn_btn3 = d(className="android.widget.TextView", textContains="赚更多金币")
                if earn_btn3.exists:
                    earn_btn3.click()
                    time.sleep(3)
                    return True
    return False


def back_to_task():
    print("开始返回任务页面")
    deadline = time.monotonic() + RETURN_TIMEOUT
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("返回淘金币任务页超时")
        temp_package, temp_activity = get_current_app(d)
        if temp_package is None or temp_activity is None or "Ext2ContainerActivity" in temp_activity:
            time.sleep(0.5)
            continue
        print(f"{temp_package}--{temp_activity}")
        if TB_APP not in temp_package:
            print(f"回到原始APP,{TB_APP}")
            start_app(d, TB_APP)
            jump_btn = d(resourceId="com.taobao.taobao:id/tv_close", text="跳过")
            if jump_btn.exists:
                jump_btn.click()
                time.sleep(2)
        else:
            if check_in_task():
                print("当前是任务列表画面，不能继续返回")
                break
            else:
                close_btn1 = d.xpath("//android.widget.FrameLayout[@resource-id='com.alipay.multiplatform.phone.xriver_integration:id/frameLayout_rightButton1']/android.widget.LinearLayout/android.widget.RelativeLayout/android.widget.RelativeLayout/android.widget.FrameLayout[2]")
                if close_btn1.exists:
                    print("点击关闭小程序按钮")
                    close_btn1.click()
                    time.sleep(1)
                    continue
                task_view = d.xpath('//android.widget.TextView[contains(@text, "限时下单任务")]')
                if task_view.exists:
                    close_btn2 = d.xpath('//android.widget.TextView[contains(@text, "限时下单任务")]/preceding-sibling::android.view.View[1]')
                    if close_btn2.exists:
                        print("点击关闭限时下单任务按钮")
                        close_btn2.click()
                        time.sleep(1)
                        continue
                print("点击后退")
                d.press("back")
                time.sleep(0.3)


handler_context = TaskHandlerContext(device=d, back_to_task=back_to_task, task_loop=task_loop)


def find_coin_btn():
    coin_btn = d(classNameMatches=r"android.widget.FrameLayout|android.view.View", description="领淘金币")
    if coin_btn.exists:
        d.double_click(coin_btn[0].center()[0], coin_btn[0].center()[1])
        time.sleep(5)
    else:
        search_bar = d(className="android.view.View", description="搜索栏")
        if not search_bar.exists(timeout=5):
            raise TimeoutError("未找到“领淘金币”入口，也未找到搜索栏")
        search_bar.click()
        d(resourceId="com.taobao.taobao:id/searchEdit").send_keys("淘金币")
        time.sleep(3)
        search_result = d(className="android.view.View", descriptionContains="淘金币")
        if not search_result.exists(timeout=5):
            raise TimeoutError("搜索“淘金币”后未找到结果")
        search_result.click()
        time.sleep(5)


def extract_task_record(view):
    info_view = view.sibling(className="android.view.View", instance=0)
    text_nodes = info_view.child(className="android.widget.TextView")
    texts = []
    for i in range(text_nodes.count):
        node = text_nodes[i]
        if node.exists:
            t = node.get_text()
            if t:
                texts.append(t)
    if not texts:
        return None

    task_name = texts[0]
    subtitle = texts[1] if len(texts) >= 2 else ""
    reward_text = " ".join(texts[2:])
    return build_task_record(
        task_name=task_name,
        subtitle=subtitle,
        button_text=view.get_text(),
        reward_text=reward_text,
    )


def discover_visible_tasks(buttons):
    tasks = []
    for view in buttons:
        task = extract_task_record(view)
        if task:
            tasks.append(task)
    return tasks


def get_task_buttons():
    return d(className="android.widget.Button", textMatches=TASK_BUTTON_PATTERN)


def scan_all_tasks():
    discovered = {}
    stagnant_rounds = 0
    scroll_count = 0
    while True:
        buttons = get_task_buttons()
        before = len(discovered)
        for task in discover_visible_tasks(buttons):
            discovered[task["task_name"]] = task
        stagnant_rounds = stagnant_rounds + 1 if len(discovered) == before else 0
        if stagnant_rounds >= 2 or scroll_count >= MAX_SCAN_SCROLLS:
            break
        d.swipe_ext("up", scale=0.45)
        time.sleep(2)
        scroll_count += 1

    for _ in range(scroll_count):
        d.swipe_ext("down", scale=0.45)
        time.sleep(1)
    return prioritize_tasks(list(discovered.values()))


def log_discovery(discovery, title):
    print(title)
    if discovery["new_tasks"]:
        print("今日新任务：", "、".join(discovery["new_tasks"]))
    if discovery["removed_tasks"]:
        print("今日消失任务：", "、".join(discovery["removed_tasks"]))
    if discovery["needs_exploration"]:
        print("待探索任务：", "、".join(discovery["needs_exploration"]))
    print("今日任务优先级：")
    for task in discovery["tasks"]:
        stats = task["stats"]
        learned_text = ""
        if stats["sample_count"]:
            learned_text = (
                f" | 样本={stats['sample_count']} | 成功率={stats['success_rate']} "
                f"| 实测={task['effective_reward']}/{task['effective_seconds']}秒"
            )
        labels = task.get("labels", {})
        matched = labels.get("_matched", [])
        label_text = f" | 标签={matched}" if matched else ""
        print(
            f"- {task['task_name']} | 动作={task['action']} | 奖励={task['reward']} | "
            f"预计={task['estimated_seconds']}秒 | 分数={task['score']} | 处理器={task['handler']}"
            f"{label_text}{learned_text}"
        )


def capture_exploration_bundle(discovery):
    if not discovery["needs_exploration"]:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    screenshot_path = LOG_DIR / f"coin-task-explore-{stamp}.png"
    hierarchy_path = LOG_DIR / f"coin-task-explore-{stamp}.xml"
    d.screenshot(str(screenshot_path))
    hierarchy_path.write_text(d.dump_hierarchy(), encoding="utf-8")
    print(f"已保存待探索任务现场：{screenshot_path.name}、{hierarchy_path.name}")


def rebuild_priority_plan(title):
    tasks = scan_all_tasks()
    discovery = refresh_catalog(tasks)
    log_discovery(discovery, title)
    capture_exploration_bundle(discovery)
    run_tracker.set_identified(len(discovery["tasks"]))
    if discovery["new_tasks"]:
        run_tracker.record_new(discovery["new_tasks"])
    return [
        task
        for task in discovery["tasks"]
        if task["action"] == "do"
        and has_task_handler(task["handler"])
        and not (task["done"] is not None and task["total"] is not None and task["done"] >= task["total"])
    ]


def remaining_high_priority_tasks():
    tasks = []
    for task in priority_plan:
        if task["score"] < HIGH_PRIORITY_MIN_SCORE:
            continue
        click_limit = max((task["total"] or 1) - (task["done"] or 0), 1)
        if have_clicked.get(task["task_name"], 0) < click_limit:
            tasks.append(task)
    return tasks


def get_latest_task_snapshot(task_name):
    latest_tasks = scan_all_tasks()
    return next((task for task in latest_tasks if task["task_name"] == task_name), None), latest_tasks


def verify_task_progress(before_task):
    after_task, latest_tasks = get_latest_task_snapshot(before_task["task_name"])
    before_done = before_task["done"]
    after_done = after_task["done"] if after_task else None
    if before_done is not None and after_done is not None and after_done > before_done:
        return True, after_task, after_done - before_done, latest_tasks, "progress_increased"
    if after_task and after_task["done"] is not None and after_task["total"] is not None and after_task["done"] >= after_task["total"]:
        return True, after_task, max((after_task["done"] or 0) - (before_done or 0), 0), latest_tasks, "already_complete"
    if after_task is None and before_task["total"] == 1 and before_task["done"] in {None, 0}:
        return True, None, 1, latest_tasks, "task_disappeared_after_single_step"
    return False, after_task, 0, latest_tasks, "no_progress"


def run_task_handler(task):
    handler = get_task_handler(task["handler"])
    handler(task, handler_context)


def build_task_candidates(buttons):
    candidates = []
    tasks = discover_visible_tasks(buttons)
    task_by_name = {task["task_name"]: task for task in tasks}
    for view in buttons:
        task = extract_task_record(view)
        if not task:
            continue

        task_name = task["task_name"]
        policy = classify_coin_task(task_name)
        if policy["action"] == "skip":
            print(f"跳过任务 [{policy['category']}] {task_name}，原因：{policy['reason']}")
            run_tracker.record_skipped(task_name, policy["category"], policy["reason"])
            if view not in unclick_btn:
                unclick_btn.append(view)
            continue

        if policy["action"] == "review":
            if task_name not in reviewed_tasks:
                print(f"跳过未分类任务 {task_name}，原因：{policy['reason']}")
                run_tracker.record_skipped(task_name, policy["category"], policy["reason"])
                reviewed_tasks.add(task_name)
            continue

        if not has_task_handler(task["handler"]):
            if task_name not in reviewed_tasks:
                print(f"跳过待探索任务 {task_name}，原因：还没有专用处理器")
                run_tracker.record_skipped(task_name, task["category"], "还没有专用处理器")
                reviewed_tasks.add(task_name)
            continue

        if task["done"] is not None and task["total"] is not None and task["done"] >= task["total"]:
            continue

        click_limit = max((task["total"] or 2) - (task["done"] or 0), 1)
        if have_clicked.get(task_name, 0) >= click_limit:
            continue

        task = task_by_name[task_name]
        candidates.append((task["score"], task_name, task, view))

    ordered_tasks = priority_plan or prioritize_tasks([candidate[2] for candidate in candidates])
    rank = {task["task_name"]: index for index, task in enumerate(ordered_tasks)}
    return sorted(candidates, key=lambda item: (rank.get(item[1], len(rank)), -item[0]))


ctx.wait_stable()
close_btn = d(className="android.widget.ImageView", description="关闭按钮")
if close_btn and close_btn.exists:
    close_btn.click()
    time.sleep(3)
find_coin_btn()

# 因2025双十一活动，需要回旧版本后继续任务
earn_btn = d(className="android.widget.Button", textContains="回日常版")
if earn_btn.exists(timeout=4):
    earn_btn.click()
    time.sleep(3)
earn_btn = d(className="android.widget.TextView", textMatches="签到领金币|点击签到")
if earn_btn.exists(timeout=4):
    earn_btn.click()
    time.sleep(5)
earn_btn = d(className="android.widget.TextView", textContains="赚更多金币")
if earn_btn.exists(timeout=4):
    earn_btn.click()
    time.sleep(3)
else:
    raise Exception("没有找到金币任务按钮")
print("点击开始做任务")
finish_count = 0
while True:
    try:
        time.sleep(4)
        check_verify(d)
        earn_btn = d(className="android.widget.TextView", text="赚更多金币")
        if earn_btn.exists and not d(className="android.widget.TextView", text="赚金币抵钱").exists:
            earn_btn.click()
            time.sleep(2)
            miss_count = 0
            consecutive_errors = 0
            continue
        draw_down_btn = d(className="android.widget.Button", text="立即领取")
        if draw_down_btn.exists:
            draw_down_btn.click()
            time.sleep(2)
            miss_count = 0
            consecutive_errors = 0
        print("开始查找按钮。。。")
        get_btn = d(className="android.widget.Button", text="领取奖励")
        if get_btn.exists:
            get_btn.click()
            print("点击领取奖励")
            time.sleep(2)
            finish_count = finish_count + 1
            miss_count = 0
            consecutive_errors = 0
            # if finish_count % 20 == 0:
            #     d.swipe_ext("up", scale=0.2)
            #     time.sleep(4)
            continue
        de_btn = d(className="android.widget.Button", text="点击得")
        if de_btn.exists:
            de_btn.click()
            print("点击点击得")
            time.sleep(4)
            miss_count = 0
            consecutive_errors = 0
            continue
        if not planned_once:
            title = "首次全量盘点" if is_first_scan_today() else "加载当日任务池"
            priority_plan = rebuild_priority_plan(title)
            planned_once = True

        if planned_once and not high_priority_rescan_done and not remaining_high_priority_tasks():
            priority_plan = rebuild_priority_plan("高优先级任务后复盘")
            high_priority_rescan_done = True

        to_btn = get_task_buttons()
        if to_btn.exists:
            candidates = build_task_candidates(to_btn)
            if not candidates and priority_plan:
                print("可见区域无候选任务，全量扫描任务列表")
                priority_plan = rebuild_priority_plan("补充扫描")
                to_btn = get_task_buttons()
                if to_btn.exists:
                    candidates = build_task_candidates(to_btn)
            if candidates:
                _, task_name, task, need_click_view = candidates[0]
                print(
                    f"点击任务 [{task['category']}] {task_name} "
                    f"(奖励={task['reward']}，预计={task['estimated_seconds']}秒，分数={task['score']})"
                )
                need_click_view.click()
                time.sleep(3.5)
                started_at = time.monotonic()
                run_task_handler(task)
                elapsed = time.monotonic() - started_at
                verified, after_task, progress_delta, latest_tasks, verify_reason = verify_task_progress(task)
                verified_reward = after_task["reward"] if after_task else task["reward"]
                record_task_outcome(
                    task,
                    seconds=elapsed,
                    reward=verified_reward if verified else 0,
                    verified=verified,
                    progress_delta=progress_delta,
                    note=verify_reason,
                )
                if verified:
                    print(
                        f"任务验收通过 {task_name}：进度 +{progress_delta}，"
                        f"实际耗时={elapsed:.1f}秒，记录奖励={verified_reward}"
                    )
                    run_tracker.record_completed(task_name, task["category"], verified_reward, elapsed, progress_delta)
                    have_clicked[task_name] = have_clicked.get(task_name, 0) + 1
                else:
                    print(f"任务验收失败 {task_name}：返回后未观察到进度变化")
                    run_tracker.record_failed(task_name, task["category"])
                priority_plan = [
                    latest_task
                    for latest_task in prioritize_tasks(latest_tasks)
                    if latest_task["action"] == "do"
                    and has_task_handler(latest_task["handler"])
                    and not (
                        latest_task["done"] is not None
                        and latest_task["total"] is not None
                        and latest_task["done"] >= latest_task["total"]
                    )
                ]
                miss_count = 0
                consecutive_errors = 0
            else:
                miss_count += 1
                print("未找到可点击按钮", miss_count)
                if miss_count >= MAX_MISS_COUNT:
                    priority_plan = rebuild_priority_plan("高优先级任务后复盘")
                    if priority_plan:
                        miss_count = 0
                        continue
                    break
        else:
            miss_count += 1
            print("未找到可点击按钮", miss_count)
            if miss_count >= MAX_MISS_COUNT:
                priority_plan = rebuild_priority_plan("任务池复盘")
                if priority_plan:
                    miss_count = 0
                    continue
                break
    except Exception as e:
        consecutive_errors += 1
        print(f"任务异常({consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): {e}")
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            raise
        continue
ctx.close()
print(f"共自动化完成{finish_count}个任务")
d.shell("settings put system accelerometer_rotation 0")
print("关闭手机自动旋转")
time2 = time.time()
minutes, seconds = divmod(int(time2 - time1), 60)
print(f"共耗时: {minutes} 分钟 {seconds} 秒")
run_tracker.generate_report()
