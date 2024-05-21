import sys, time
from enum import Enum  # 枚举类
from functools import partial  # 使button的connect函数可带参数
from elevator.ele import *
from PyQt5.QtGui import QFont, QColor, QBrush, QPixmap
from PyQt5.QtCore import QRect, QThread, QMutex, QTimer
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QLabel, QTextEdit, QVBoxLayout, QHBoxLayout, QLCDNumber, \
    QLineEdit
for qwerty in range(ELEVATOR_NUM):
    # inner_requests.append([])  # add list
    elevator_states.append(ElevatorState.normal)  # 默认正常
    cur_floor.append(1)  # 默认在1楼
    up_targets.append([])
    down_targets.append([])
    is_close_button_clicked.append(False)  # 默认开门关门键没按
    is_open_button_clicked.append(False)
    move_states.append(MoveState.none)  # 默认闲置
    open_progress.append(0.0)  # 默认门没开 即进度条停在0.0

# 互斥锁
mutex = QMutex()


class direction(QThread):
    def __init__(self):
        super().__init__()  # 父类构造函数

    def run(self):
        while True:
            mutex.lock()
            global outer_requests
            # direction只处理外面按钮产生的任务安排
            # 找到距离最短的电梯编号
            for outer_task in outer_requests:
                if outer_task.state == OuterTaskState.unassigned:  # 如果未分配..
                    min_distance = ELEVATOR_FLOORS + 1
                    target_id = -1
                    for iii in range(ELEVATOR_NUM):
                        # 符合要求的电梯，必须没有故障
                        if elevator_states[iii] == ElevatorState.fault:
                            continue

                        # 如果已经上行/下行了 就设成已经到达目的地的楼层了
                        origin = cur_floor[iii]
                        if elevator_states[iii] == ElevatorState.going_up:
                            origin += 1
                        elif elevator_states[iii] == ElevatorState.going_down:
                            origin -= 1

                        if move_states[iii] == MoveState.up:
                            targets = up_targets[iii]
                        else:  # down
                            targets = down_targets[iii]
                        # 本身对某一种方向来说，根据这部电梯是否与它运行方向相同，是在上方还是下方，是否有任务，分为8种情况..
                        # 如果电梯运行方向无任务，则直接算绝对值
                        if not targets:
                            distance = abs(origin - outer_task.target)
                        # 如果电梯朝着按键所在楼层而来 且运行方向与理想方向相同 也是直接绝对值
                        elif move_states[iii] == outer_task.move_state and \
                                ((outer_task.move_state == MoveState.up and outer_task.target >= origin) or
                                 (outer_task.move_state == MoveState.down and outer_task.target <= origin)):
                            distance = abs(origin - outer_task.target)
                        # 其余情况则算最远任务楼层到目标楼层的绝对值和最远楼层到当前电梯楼层的绝对值之和
                        else:
                            distance = abs(origin - targets[-1]) + abs(outer_task.target - targets[-1])

                        # 寻找最小值
                        if distance < min_distance:
                            min_distance = distance
                            target_id = iii

                    # 假如找到了 对应添加任务..
                    if target_id != -1:
                        if cur_floor[target_id] == outer_task.target:
                            if outer_task.move_state == MoveState.up and outer_task.target not in up_targets[target_id] and elevator_states[target_id] != ElevatorState.going_up:
                                up_targets[target_id].append(outer_task.target)
                                up_targets[target_id].sort()
                                print(up_targets)
                                # 设为等待态
                                outer_task.state = OuterTaskState.waiting

                            elif outer_task.move_state == MoveState.down and outer_task.target not in down_targets[target_id] and elevator_states[target_id] != ElevatorState.going_down:
                                down_targets[target_id].append(outer_task.target)
                                down_targets[target_id].sort(reverse=True)  # 降序
                                print(down_targets)
                                # 设为等待态
                                outer_task.state = OuterTaskState.waiting

                        elif cur_floor[target_id] < outer_task.target and outer_task.target not in up_targets[target_id]:  # up
                            up_targets[target_id].append(outer_task.target)
                            up_targets[target_id].sort()
                            print(up_targets)
                            # 设为等待态
                            outer_task.state = OuterTaskState.waiting
                        elif cur_floor[target_id] > outer_task.target and outer_task.target not in down_targets[target_id]:  # down
                            down_targets[target_id].append(outer_task.target)
                            down_targets[target_id].sort(reverse=True)  # 降序
                            print(down_targets)
                            # 设为等待态
                            outer_task.state = OuterTaskState.waiting

            # 查看哪些任务已经完成了 移除已经完成的..
            outer_requests = [task for task in outer_requests if task.state != OuterTaskState.finished]

            mutex.unlock()


class Elevator(QThread):

    def __init__(self, elevator_s):
        super().__init__()  # 父类构造函数
        self.elevator_s = elevator_s  # 电梯编号
        self.time_slice = 10  # 时间间隔（单位：毫秒）

    # 移动一层楼
    # 方向由参数确定 可以是
    # MoveState.up or MoveState.down
    def move_one_f(self, move_state):
        # 修改电梯运行状态
        if move_state == MoveState.up:
            elevator_states[self.elevator_s] = ElevatorState.going_up
        elif move_state == MoveState.down:
            elevator_states[self.elevator_s] = ElevatorState.going_down
        else:
            elevator_states[self.elevator_s] = ElevatorState.normal
        has_slept_time = 0
        while has_slept_time != TIME_PER_FLOOR:
            # 需要先放开锁 不然别的线程不能运行
            mutex.unlock()
            self.msleep(self.time_slice)
            has_slept_time += self.time_slice
            # 锁回来
            mutex.lock()
            # 故障判断
            if elevator_states[self.elevator_s] == ElevatorState.fault:
                self.fault_tackle()
                return

        if move_state == MoveState.up:
            cur_floor[self.elevator_s] += 1
        elif move_state == MoveState.down:
            cur_floor[self.elevator_s] -= 1
        elevator_states[self.elevator_s] = ElevatorState.normal
        if elevator_states[self.elevator_s] == ElevatorState.fault:
            self.fault_tackle()

    # 开门关门
    def door(self):
        opening_time = 0.0
        open_time = 0.0
        elevator_states[self.elevator_s] = ElevatorState.opening_door
        while True:
            # 故障直接结束
            if elevator_states[self.elevator_s] == ElevatorState.fault:
                self.fault_tackle()
                break

            elif is_open_button_clicked[self.elevator_s]:  # 要打开
                # 门正在关上..
                if elevator_states[self.elevator_s] == ElevatorState.closing_door:
                    elevator_states[self.elevator_s] = ElevatorState.opening_door
                # 门已经开了
                elif elevator_states[self.elevator_s] == ElevatorState.open_door:
                    open_time = 0  # 时间归零

                is_open_button_clicked[self.elevator_s] = False

            elif is_close_button_clicked[self.elevator_s]:  # 要关上
                elevator_states[self.elevator_s] = ElevatorState.closing_door
                open_time = 0  # 时间归零

                is_close_button_clicked[self.elevator_s] = False

            # 更新时间
            # 门正在打开
            if elevator_states[self.elevator_s] == ElevatorState.opening_door:
                # 需要先放开锁 不然别的线程不能运行
                mutex.unlock()
                self.msleep(self.time_slice)
                opening_time += self.time_slice
                # 锁回来
                mutex.lock()
                open_progress[self.elevator_s] = opening_time / OPENING_DOOR_TIME
                if opening_time == OPENING_DOOR_TIME:
                    elevator_states[self.elevator_s] = ElevatorState.open_door

            # 门已打开
            elif elevator_states[self.elevator_s] == ElevatorState.open_door:
                # 需要先放开锁 不然别的线程不能运行
                mutex.unlock()
                self.msleep(self.time_slice)
                open_time += self.time_slice
                # 锁回来
                mutex.lock()
                if open_time == OPEN_DOOR_TIME:
                    elevator_states[self.elevator_s] = ElevatorState.closing_door

            # 门正在关闭
            elif elevator_states[self.elevator_s] == ElevatorState.closing_door:
                # 需要先放开锁
                mutex.unlock()
                self.msleep(self.time_slice)
                opening_time -= self.time_slice
                # 锁回来
                mutex.lock()
                open_progress[self.elevator_s] = opening_time / OPENING_DOOR_TIME
                if opening_time == 0:
                    # 关门
                    elevator_states[self.elevator_s] = ElevatorState.normal
                    break

    # 当故障发生时 清除原先的所有任务
    def fault_tackle(self):
        open_progress[self.elevator_s] = 0.0
        is_open_button_clicked[self.elevator_s] = False
        is_close_button_clicked[self.elevator_s] = False
        for outer_task in outer_requests:
            if outer_task.state == OuterTaskState.waiting:
                if outer_task.target in up_targets[self.elevator_s] or outer_task.target in down_targets[self.elevator_s]:
                    outer_task.state = OuterTaskState.unassigned  # 把原先分配给它的任务交给direction重新分配
        up_targets[self.elevator_s] = []  # 全部清零
        down_targets[self.elevator_s] = []

    # 具体运行
    def run(self):
        while True:
            mutex.lock()
            if elevator_states[self.elevator_s] == ElevatorState.fault:
                self.fault_tackle()
                mutex.unlock()
                continue

            # 向上扫描状态时
            if move_states[self.elevator_s] == MoveState.up:
                if up_targets[self.elevator_s]:
                    if up_targets[self.elevator_s][0] == cur_floor[self.elevator_s]:
                        self.door()
                        # 到达以后 把完成的任务删去
                        # 内部的任务
                        if up_targets[self.elevator_s]:
                            up_targets[self.elevator_s].pop(0)
                        # 外部按钮的任务
                        for outer_task in outer_requests:
                            if outer_task.target == cur_floor[self.elevator_s]:
                                outer_task.state = OuterTaskState.finished  # 交给direction处理
                    elif up_targets[self.elevator_s][0] > cur_floor[self.elevator_s]:
                        self.move_one_f(MoveState.up)

                # 当没有上行目标而出现下行目标时 更换状态
                elif up_targets[self.elevator_s] == [] and down_targets[self.elevator_s] != []:
                    move_states[self.elevator_s] = MoveState.down
                else:
                    move_states[self.elevator_s] = MoveState.none

            # 向下扫描状态时
            elif move_states[self.elevator_s] == MoveState.down:
                if down_targets[self.elevator_s]:
                    if down_targets[self.elevator_s][0] == cur_floor[self.elevator_s]:
                        self.door()
                        # 到达以后 把完成的任务删去
                        # 内部的任务
                        if down_targets:
                            if down_targets[self.elevator_s]:
                                down_targets[self.elevator_s].pop(0)
                        # 外部按钮的任务
                        for outer_task in outer_requests:
                            if outer_task.target == cur_floor[self.elevator_s]:
                                outer_task.state = OuterTaskState.finished

                    elif down_targets[self.elevator_s][0] < cur_floor[self.elevator_s]:
                        self.move_one_f(MoveState.down)

                # 当没有下行目标而出现上行目标时 更换状态
                elif down_targets[self.elevator_s] == [] and up_targets[self.elevator_s] != []:
                    move_states[self.elevator_s] = MoveState.up
                else:
                    move_states[self.elevator_s] = MoveState.none

            # 没有任务了
            elif move_states[self.elevator_s] == MoveState.none:
                if down_targets[self.elevator_s] == [] and up_targets[self.elevator_s] != []:
                    move_states[self.elevator_s] = MoveState.up
                elif up_targets[self.elevator_s] == [] and down_targets[self.elevator_s] != []:
                    move_states[self.elevator_s] = MoveState.down
                # else:
                #     if 1 < cur_floor[self.elevator_s]:
                #         self.move_one_f(MoveState.down)

            mutex.unlock()


# 图形化界面 同时处理画面更新和输入
class ElevatorUi(QWidget):
    def __init__(self):
        super().__init__()  # 父类构造函数
        self.output = None
        # 定时更新UI界面
        self.timer = QTimer()
        # 错误列表
        self.faulty = []
        self.floor = []       # 楼层
        self.__outer_up = []
        self.__outer_down = []
        self.num_display = []
        self.inner_open = []
        self.inner_close = []
        self.label = []
        self.time_slice = 0.01  # 时间间隔（单位：毫秒）
        # 设置UI
        self.background()
        self.setup_ui()
        # 一开始的电梯设置为空闲
        elevator_states[0] = ElevatorState.normal
        elevator_states[1] = ElevatorState.normal
        elevator_states[2] = ElevatorState.normal
        elevator_states[3] = ElevatorState.normal
        elevator_states[4] = ElevatorState.normal
    # 设置背景图片

    def background(self):
        lbl = QLabel(self)
        lbl.setGeometry(0, 0, 1400, 1800)
        pixmap = QPixmap("e.jpg")  # 按指定路径找到图片
        lbl.setPixmap(pixmap)  # 在label上显示图片
        lbl.setScaledContents(True)  # 让图片自适应label大小

    def setup_ui(self):

        self.setWindowTitle("elevator simulator")
        self.setGeometry(UI_SIZE)

        h1 = QHBoxLayout()
        self.setLayout(h1)
        v3 = QVBoxLayout()
        h1.addLayout(v3)
        v3.setContentsMargins(0, 65, 0, 98)
        v3.setSpacing(5)

        for i in range(ELEVATOR_FLOORS):
            h4 = QHBoxLayout()
            v3.addLayout(h4)
            label = QLabel(str(ELEVATOR_FLOORS - i))
            label.setStyleSheet("color:white")
            h4.addWidget(label)
            if i != 0:
                # 上行按钮
                up_button = QPushButton("↑")
                up_button.setFixedSize(30, 30)
                up_button.clicked.connect(
                    partial(self.__outer_direction_button_clicked, ELEVATOR_FLOORS - i, MoveState.up))
                self.__outer_up.append(up_button)  # 从顶楼往下一楼开始
                h4.addWidget(up_button)

            if i != ELEVATOR_FLOORS - 1:
                # 下行按钮
                down_button = QPushButton("↓")
                down_button.setFixedSize(30, 30)
                down_button.clicked.connect(
                    partial(self.__outer_direction_button_clicked, ELEVATOR_FLOORS - i, MoveState.down))
                self.__outer_down.append(down_button)  # 从顶楼开始到2楼
                h4.addWidget(down_button)
        h2 = QHBoxLayout()
        h1.addLayout(h2)

        for i in range(ELEVATOR_NUM):
            v2 = QVBoxLayout()
            h2.addLayout(v2)
            # 电梯上方的LCD显示屏
            floor_display = QLCDNumber()
            floor_display.setStyleSheet("color:white")
            floor_display.setFixedSize(140, 70)
            self.floor.append(floor_display)
            v2.addWidget(floor_display)
            self.num_display.append([])
            for j in range(ELEVATOR_FLOORS):
                # 内部数字按键
                button = QPushButton(str(ELEVATOR_FLOORS - j))
                button.setFixedSize(140, 40)
                button.clicked.connect(partial(self.__inner_num_button_clicked, i, ELEVATOR_FLOORS - j))
                button.setStyleSheet("background-color : rgb(100,200,200)")
                self.num_display[i].append(button)
                v2.addWidget(button)
            # 故障按钮
            fault_button = QPushButton("error!")
            fault_button.setFixedSize(140, 50)
            fault_button.clicked.connect(partial(self.__inner_fault_button_clicked, i))
            fault_button.setStyleSheet("background-color : rgb(100,200,200)")
            self.faulty.append(fault_button)
            v2.addWidget(fault_button)
            h3 = QHBoxLayout()
            # 开门按钮
            open_button = QPushButton("开")
            open_button.setFixedSize(62, 50)
            open_button.clicked.connect(partial(self.inner_open_button_clicked, i))
            self.inner_open.append(open_button)
            # 关门按钮
            close_button = QPushButton("关")
            close_button.setFixedSize(62, 50)
            close_button.clicked.connect(partial(self.inner_close_button_clicked, i))
            self.inner_close.append(close_button)
            v2.addLayout(h3)
            h3.addWidget(open_button)
            h3.addWidget(close_button)

        v1 = QVBoxLayout()
        h1.addLayout(v1)
        label1 = QLabel("ELEVATOR SIMULATOR\n")
        label1.setFont(QFont('times', 14, QFont.Black))  # 设置字体
        label1.setStyleSheet("color:white")
        label2 = QLabel("直接按下数字键让电梯前往该层\n使用↑↓键表示此楼有人需要搭乘\n↑↓变成粉色表示有人需要上电梯\n蓝色渐变表示开门关门\n")
        label2.setFont(QFont('times', 10, QFont.OldEnglish))  # 设置字体
        label2.setStyleSheet("color:white")
        v1.addWidget(label1)
        v1.addWidget(label2)
        v3 = QVBoxLayout()
        h3.addLayout(v3)

        # 输出电梯信息
        self.output = QTextEdit()
        self.output.setFont(QFont("宋体", 10, QFont.Bold))  # 定义格式字体
        self.output.setText("电梯运转实况表：\n")
        v1.addWidget(self.output)
        # 设置定时
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.show()

    def inner_open_button_clicked(self, elevator_id):  # 开门
        mutex.lock()
        opening_time = 0.0  # 初始化
        if elevator_states[elevator_id] == ElevatorState.fault:
            self.output.append(str(elevator_id) + "号电梯出现故障 正在维修!")
            mutex.unlock()
            return

        if elevator_states[elevator_id] == ElevatorState.normal:
            is_open_button_clicked[elevator_id] = True
            is_close_button_clicked[elevator_id] = False
            elevator_states[elevator_id] = ElevatorState.forced
            self.num_display[elevator_id][ELEVATOR_FLOORS - cur_floor[elevator_id]].setStyleSheet(
                "background-color : rgb(200,250,200)")
            self.inner_open[elevator_id].setStyleSheet("background-color : yellow")
            self.output.append(str(elevator_id) + "电梯开门!")
            while True:
                if elevator_states[elevator_id] == ElevatorState.forced:
                    # 需要先放开锁 不然别的线程不能运行
                    mutex.unlock()
                    time.sleep(self.time_slice)
                    opening_time += self.time_slice
                    # 锁回来
                    mutex.lock()
                    open_progress[elevator_id] = opening_time / OPENING_DOOR_TIME2
                    if int(opening_time) == OPENING_DOOR_TIME2:
                        elevator_states[elevator_id] = ElevatorState.forced_open
                        is_open_button_clicked[elevator_id] = False
                        break
        elif elevator_states[elevator_id] == ElevatorState.closing_door:
            self.inner_open[elevator_id].setStyleSheet("background-color : red")
            self.output.append(str(elevator_id) + "电梯关门中")
        else:
            self.inner_open[elevator_id].setStyleSheet("background-color : red")
            self.output.append(str(elevator_id) + "电梯运行中")
        mutex.unlock()

    def inner_close_button_clicked(self, elevator_id):  # 关门
        mutex.lock()
        opening_time = 0.0  # 初始化
        if elevator_states[elevator_id] == ElevatorState.fault:
            self.output.append(str(elevator_id) + "号电梯出现故障 正在维修!")
            mutex.unlock()
            return

        if elevator_states[elevator_id] == ElevatorState.forced_open or\
                elevator_states[elevator_id] == ElevatorState.forced:
            is_close_button_clicked[elevator_id] = True
            is_open_button_clicked[elevator_id] = False
            elevator_states[elevator_id] = ElevatorState.closing_door
            self.num_display[elevator_id][ELEVATOR_FLOORS - cur_floor[elevator_id]].setStyleSheet(
                "background-color : rgb(100,200,200)")
            self.inner_close[elevator_id].setStyleSheet("background-color : yellow")
            self.output.append(str(elevator_id) + "电梯关门!")
            while True:
                # 门正在关闭
                if elevator_states[elevator_id] == ElevatorState.closing_door:
                    # 需要先放开锁
                    mutex.unlock()
                    time.sleep(self.time_slice)
                    opening_time += self.time_slice
                    # 锁回来
                    mutex.lock()
                    open_progress[elevator_id] = opening_time / OPENING_DOOR_TIME2
                    if int(opening_time) == OPENING_DOOR_TIME2:
                        # 关门
                        elevator_states[elevator_id] = ElevatorState.normal
                        is_close_button_clicked[elevator_id] = False
                        break
        else:
            self.inner_close[elevator_id].setStyleSheet("background-color : red")
            self.output.append(str(elevator_id) + "电梯已处于关门或将要关门状态！")
        mutex.unlock()

    def __inner_fault_button_clicked(self, elevator_id):
        time.sleep(0.05)  # 防止出现任务清空失败
        mutex.lock()
        if elevator_states[elevator_id] != ElevatorState.fault:
            elevator_states[elevator_id] = ElevatorState.fault
            mutex.unlock()  # 解锁
            self.faulty[elevator_id].setStyleSheet("background-color : yellow")
            for button in self.num_display[elevator_id]:
                button.setStyleSheet("background-color : rgb(100,200,200)")
            self.inner_open[elevator_id].setStyleSheet("background-color : rgb(100,200,200)")
            self.inner_close[elevator_id].setStyleSheet("background-color : rgb(100,200,200)")

            self.output.append(str(elevator_id) + "电梯出现故障")

        else:
            elevator_states[elevator_id] = ElevatorState.normal
            mutex.unlock()

            self.faulty[elevator_id].setStyleSheet("background-color : rgb(100,200,200)")
            self.output.append(str(elevator_id) + "电梯恢复")

    def __inner_num_button_clicked(self, elevator_id, floor):
        mutex.lock()

        if elevator_states[elevator_id] == ElevatorState.fault:
            self.output.append(str(elevator_id) + "号电梯故障中")
            mutex.unlock()
            return
        # 判断是否是强制打开
        if elevator_states[elevator_id] == ElevatorState.forced_open or \
                elevator_states[elevator_id] == ElevatorState.forced:
            self.output.append(str(elevator_id) + "号电梯打开中")
            mutex.unlock()
            return
        # 相同楼层不处理
        if floor == cur_floor[elevator_id]:
            mutex.unlock()
            return

        if elevator_states[elevator_id] != ElevatorState.fault:
            self.num_display[elevator_id][ELEVATOR_FLOORS - cur_floor[elevator_id]].setStyleSheet("background-color : rgb(100,200,200)")
            if floor > cur_floor[elevator_id] and floor not in up_targets[elevator_id]:
                up_targets[elevator_id].append(floor)
                up_targets[elevator_id].sort()
            elif floor < cur_floor[elevator_id] and floor not in down_targets[elevator_id]:
                down_targets[elevator_id].append(floor)
                down_targets[elevator_id].sort(reverse=True)  # 降序 例如[20,19..]
            mutex.unlock()

            self.num_display[elevator_id][ELEVATOR_FLOORS - floor].setStyleSheet("background-color : yellow")
            self.output.append(str(elevator_id) + "号电梯" + "的用户请求前往" + str(floor) + "楼")

    def __outer_direction_button_clicked(self, floor, move_state):
        mutex.lock()
        # 错误检测
        all_fault_flag = True
        for state in elevator_states:
            if state != ElevatorState.fault:
                all_fault_flag = False

        if all_fault_flag:
            self.output.append("无完善电梯")
            mutex.unlock()
            return
        #开门检测
        all_open_flag = True
        for state in elevator_states:
            if state != ElevatorState.forced_open and state != ElevatorState.forced:
                all_open_flag = False
        if all_open_flag:
            self.output.append("电梯全部被打开")
            mutex.unlock()
            return
        task = OuterTask(floor, move_state)

        if task not in outer_requests:
            outer_requests.append(task)
            self.output.append("来自"+ str(floor) + "楼的请求")
        mutex.unlock()

    def update(self):
        mutex.lock()
        for i in range(ELEVATOR_NUM):
            # 实时更新楼层
            if elevator_states[i] == ElevatorState.going_up:
                self.floor[i].display("↑" + str(cur_floor[i]))
            elif elevator_states[i] == ElevatorState.going_down:
                self.floor[i].display("↓" + str(cur_floor[i]))
            else:
                self.floor[i].display(cur_floor[i])

            # 实时更新开关门按钮
            if not is_open_button_clicked[i]:
                self.inner_open[i].setStyleSheet("background-color :  rgb(210,250,200)")

            if not is_close_button_clicked[i]:
                self.inner_close[i].setStyleSheet("background-color :  rgb(210,250,200)")

            # 对内部的按钮，如果在开门或关门状态的话，则设进度条
            if elevator_states[i] in [ElevatorState.opening_door, ElevatorState.open_door, ElevatorState.closing_door]:
                self.num_display[i][ELEVATOR_FLOORS - cur_floor[i]].setStyleSheet(
                    "background-color : rgb(100," + str(int(200 * (1 - open_progress[i]))) + ",200)")

        mutex.unlock()
        # 对外部来说，遍历任务，找出未完成的设为红色，其他设为默认原色
        for button in self.__outer_up:
            button.setStyleSheet("background-color : rgb(200,200,250)")

        for button in self.__outer_down:
            button.setStyleSheet("background-color : rgb(200,200,250)")

        mutex.lock()
        for outer_task in outer_requests:
            if outer_task.state != OuterTaskState.finished:
                if outer_task.move_state == MoveState.up:
                    self.__outer_up[ELEVATOR_FLOORS - outer_task.target - 1].setStyleSheet(
                        "background-color : pink")
                elif outer_task.move_state == MoveState.down:
                    self.__outer_down[ELEVATOR_FLOORS - outer_task.target].setStyleSheet(
                        "background-color : pink")

        mutex.unlock()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 开启线程
    direction = direction()
    direction.start()

    elevators = []  # 电梯数量
    for i in range(ELEVATOR_NUM):
        elevators.append(Elevator(i))

    for elevator in elevators:
        elevator.start()

    e = ElevatorUi()
    sys.exit(app.exec_())
