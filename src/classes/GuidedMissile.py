import numpy as np

from src.classes.ModelDispatcher import ModelDispatcher
from src.classes.Movable import Movable
from src.messages.BaseMessage import BaseMessage
from config.constants import (MSG_CCP2GM_type, GuidedMissile_SPEED,
                              GuidedMissile_LifeTime, GuidedMissile_ExplRadius, GuidedMissile_MaxRotAngle)


def unit_vector(vector):
    """ Returns the unit vector of the vector.  """
    return vector / np.linalg.norm(vector)


def angle_between(v1, v2):
    """ Returns the angle in radians between vectors 'v1' and 'v2'::

            >>> angle_between((1, 0, 0), (0, 1, 0))
            1.5707963267948966
            >>> angle_between((1, 0, 0), (1, 0, 0))
            0.0
            >>> angle_between((1, 0, 0), (-1, 0, 0))
            3.141592653589793
    """
    v1_u = unit_vector(v1)
    v2_u = unit_vector(v2)
    return np.arccos(np.clip(np.dot(v1_u, v2_u), -1.0, 1.0))
class GuidedMissile(Movable):
    def __init__(self, dispatcher: ModelDispatcher, ID: int,
                 pos: np.array,
                 speed=GuidedMissile_SPEED,
                 life_time=GuidedMissile_LifeTime,
                 expl_radius=GuidedMissile_ExplRadius) -> None:
        """
        :param dispatcher: диспетчер, для синхронизации с другими модулями
        :param ID: ID этой ракеты
        :param pos: position of guide missile (x,y,z)
        :param speed:
        :param life_time: возможное время жизни ракеты
        :param expl_radius: радиус взрыва ракеты
        """
        super(GuidedMissile, self).__init__(dispatcher, ID, pos, None)
        self.speed = speed
        self.pos_target = None
        self.life_time = life_time
        self.expl_radius = expl_radius
        self.pos_target = None
        self.__status = 0
        self.launch_time = None
        self.__previous_time = None

    def launch(self, pos_target: np.array, launch_time: float) -> None:
        """
        :param pos_target: np array of coordinates (x, y, z)
        :param launch_time: время запуска
        """
        self.pos_target = pos_target
        self.vel = (self.pos_target - self.pos) / np.linalg.norm(self.pos_target - self.pos) * self.speed
        self.launch_time = launch_time
        self.__previous_time = launch_time
        self.__status = 1
        # print(f"Base target pos: {self.pos_target}, Base Guide missile pos: {self.pos}")
        
    def updateTarget(self, pos_target: np.array) -> None:
        """
        Обновление координат цели
        :param pos_target: np.array of [x,y,z]
        """
        self.pos_target = pos_target

    def updateCoordinate(self) -> None:
        """
        Обновление координат ракеты
        :param time: сколько времени ракета летела с прошлого обновления координат
        """
        vel_old = self.vel.copy()
        self.vel = (self.pos_target - self.pos) / np.linalg.norm(self.pos_target - self.pos) * self.speed
        # print(angle_between(self.vel, vel_old), self.vel, self._simulating_tick)
        if angle_between(self.vel, vel_old) > GuidedMissile_MaxRotAngle:
            # print("too big angle")
            self.vel = (self.vel + vel_old) / np.linalg.norm(self.vel + vel_old) * self.speed
        self.pos = self.pos + self.vel*self._simulating_tick

    def checkIsHit(self):
        """
        Проверка поражена ли цель
        """
        if (((self.pos - self.pos_target) ** 2).sum())**0.5 < self.expl_radius:
            self.__status = 2
        print(f"Distance to target {(((self.pos - self.pos_target) ** 2).sum()) ** 0.5}")

    def getStatus(self):
        """
        Узнать статус ракеты
        0 - не активна
        1 - летит
        2 - поразила цель
        3 - пропустила цель, закончилось топливо
        :return:
        """
        return self.__status

    def runSimulationStep(self, time):
        """
        Шаг симуляции ракеты
        MSG_CCP2GM_type, сообщения корректирующие положение цели
        :param time: текущее время в симуляции
        """
        messages = self._checkAvailableMessagesByType(msg_type=MSG_CCP2GM_type)
        messages.sort(key=lambda x: x.priority, reverse=True)

        pos_target = self.pos_target

        if len(messages) != 0:

            pos_target = messages[0].new_target_coord
            print(f"ЗУР получила сообщение, новые координаты: {pos_target}")

        if self.__status == 1:
            self.updateTarget(pos_target)
            self.updateCoordinate()
            self.checkIsHit()
            if self.__status == 2:
                print(f"HIT Target: {self.pos_target[0]}, {self.pos_target[1]}, {self.pos_target[2]}, is hit by Rocket with ID {self._ID}")
            elif time - self.launch_time > self.life_time:
                self.__status = 3
                print(f"MISS Target: {self.pos_target[0]}, {self.pos_target[1]}, {self.pos_target[2]}, is miss, Rocket with ID {self._ID} fell")

        if self.__status > 1:
            print(f"Rocket with ID {self._ID} was destroyed, with status: {self.__status}")

        self.__previous_time = time
        #print(f"ID: {self._ID}, Rokcet coordinate {self.x}, {self.y}, {self.z}")