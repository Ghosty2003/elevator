import sys
from enum import Enum  # 枚举类
from functools import partial  # 使button的connect函数可带参数
from PyQt5.QtCore import QRect, QThread, QMutex, QTimer
from PyQt5.QtWidgets import QWidget, QPushButton, QApplication, QLabel, QTextEdit, QVBoxLayout, QHBoxLayout, QLCDNumber, \
    QLineEdit


# 电梯的状态 包括正常 开门中 开门 关门中 上行中 下行中 故障 空闲 强行打开
class ElevatorState(Enum):
    normal = 0
    opening_door = 1
    open_door = 2
    closing_door = 3
    fault = 4
    going_up = 5
    going_down = 6
    nothing = 7
    forced = 8
    forced_open = 9

# 电梯的扫描移动状态 包括 向上 向下 空闲
class MoveState(Enum):
    up = 2
    down = 3
    none = 4


# 外部按钮产生的任务的分配状态 包括未分配 等待 完成
class OuterTaskState(Enum):
    unassigned = 1
    waiting = 2
    finished = 3


# 外部按钮按下产生的任务描述
class OuterTask:
    def __init__(self, target, move_state, state=OuterTaskState.unassigned):  # the task is unfinished by default
        self.target = target  # 目标楼层
        self.move_state = move_state  # 需要的电梯运行方向
        self.state = state  # 是否完成（默认未完成）


# 窗口大小设置
UI_SIZE = QRect(300, 300, 800, 1000)

# 一些全局变量
ELEVATOR_NUM = 5  # 电梯数量
ELEVATOR_FLOORS = 20  # 电梯层数

TIME_PER_FLOOR = 800  # 运行一层电梯所需平均时间 单位 毫秒
OPENING_DOOR_TIME = 1000  # 打开一扇门所需时间 单位 毫秒
OPEN_DOOR_TIME = 1000  # 门打开后维持的时间 单位 毫秒
# 秒制
OPENING_DOOR_TIME2 = 1
# 外部按钮产生的需求
outer_requests = []
# 每组电梯的状态
elevator_states = []
# 每台电梯的当前楼层
cur_floor = []
# 每台电梯当前需要向上运行处理的目标有哪些（二维数组，内部int）
up_targets = []
# 每台电梯当前需要向下运行处理的目标有哪些（二维数组，内部int）
down_targets = []
# 每台电梯内部的开门/关门键是否被按（True/False）
is_open_button_clicked = []
is_close_button_clicked = []
# 每台电梯当前的扫描运行状态
move_states = []
# 每台电梯开门的进度条 范围为0-1的浮点数
open_progress = []
