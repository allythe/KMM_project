import numpy as np

from simulation_process.constants import MSG_CCP2RADAR_type, TARGET_TYPE_DRAWER, DRAWER_ID, MSG_GM2RADAR_type, DISPATCHER_ID, EPS, \
    MAX_ERROR_DIST, RATE_ERROR_SPEED, MIN_DIST_DETECTION
from simulation_process.messages_classes.Messages import Radar2CombatControlMsg, Radar2MissileMsg, Radar2DrawerMsg, \
    GuidedMissileHit2CCPMsg, Radar_InitMessage, Radar_ViewMessage
from simulation_process.modules_classes.Simulated import Simulated
from simulation_process.modules_classes.AeroEnv import AeroEnv
from logs.logger import logger


class RadarRound(Simulated):
    def __init__(self, dispatcher, ID: int, cp_ID: int, aero_env: AeroEnv,
                 pos: np.array, pan_start, tilt_start, view_distance: int,
                 pan_per_sec: float, tilt_per_sec: float):
        """ Класс, описывающий работу РЛС кругового типа обзора, является родительским классом
         для РЛС секторного типа обзора:
         :param dispatcher: ссылка на объект диспетчера
         :param ID: собственный ID
         :param cp_ID: ID ПБУ
         :param pos: координаты положения РЛС, относительно глобальной СК (x, y, z)
         :param pan_start: начальное положение по углу поворота относительно глобальной СК в градусах
         :param tilt_start: начальное положение по углу наклона относительно глобальной СК в градусах
         :param view_distance: дальность обзора РЛС
         :param pan_per_sec: угол раскрыва по углу поворота за секунду обзора в градусах
         :param tilt_per_sec: угол раскрыва по углу наклона за секунду обзора в градусах"""
        super().__init__(dispatcher, ID, pos)
        self.cp_ID = cp_ID
        self.aero_env = aero_env
        self.pan_start = pan_start
        self.tilt_start = tilt_start  # на потом

        self.pan_cur = pan_start  # начало секундного сектора обзора в данный момент времени по углу поворота
        self.tilt_cur = tilt_start  # начало секундного сектора обзора в данный момент времени по углу наклона

        # параметры зависящие от типа рлс
        self.view_distance = view_distance
        self.pan_per_sec = pan_per_sec
        self.tilt_per_sec = tilt_per_sec

        self.start = True

    def findObjects(self):
        all_objects = self.aero_env.getEntities()
        visible_objects = []
        logger.radar(f"Radar с id {self._ID} видит по углу поворота от {self.pan_cur} до {self.pan_cur + self.pan_per_sec}")
        logger.radar(
            f"Radar с id {self._ID} видит по углу наклона от {self.tilt_cur} до {self.tilt_cur + self.tilt_per_sec}")
        for obj in all_objects:
            r = np.linalg.norm(obj.pos - self.pos)
            # logger.radar(f"радар чекает объект с координатами {obj.pos}, дальность {r}")

            if MIN_DIST_DETECTION < r < self.view_distance:
                x, y, z = (obj.pos - self.pos)
                tilt = np.rad2deg(np.arcsin(z / (r + EPS))) % 180
                pan = np.rad2deg(np.arctan2(y, (x + EPS))) % 360

                # logger.radar(f"радар чекает объект с pan {pan}, с tilt {tilt}, pan_cur {self.pan_cur}, pan per sec {self.pan_per_sec}, tilt cur {self.tilt_cur}, tilt per sec {self.tilt_per_sec}")

                if self.pan_cur < pan < self.pan_cur + self.pan_per_sec and self.tilt_cur < tilt < self.tilt_cur + self.tilt_per_sec:
                    logger.radar(
                        f"Radar с id {self._ID} видит объект с сферическими координатами (dist, pan, tilt): {r, pan, tilt}")
                    logger.radar(
                        f"Radar с id {self._ID} видит объект с  координатами x, y, z: {x, y, z}")
                    error_dist = np.random.randint(-MAX_ERROR_DIST, MAX_ERROR_DIST, size=3)
                    pos = obj.pos + error_dist
                    error_r = int(np.mean(error_dist)) + 1

                    speed = np.linalg.norm(obj.vel)
                    error_vel = np.random.randint(-int(RATE_ERROR_SPEED * speed) - 1, int(RATE_ERROR_SPEED * speed) + 1,
                                                                      size=3)
                    velocity_from_radar = obj.vel + error_vel
                    speed_from_radar = np.linalg.norm(velocity_from_radar)
                    visible_objects.append([pos, velocity_from_radar, speed_from_radar, error_r])

        logger.radar(f"Radar с id {self._ID} видит {len(visible_objects)} объектов")
        return visible_objects

    def moveToNextSector(self):
        # винтовой обзор
        logger.radar(
            f"Radar ID {self._ID} видит от {self.pan_cur} до {self.pan_cur + self.pan_per_sec} по углу поворота")
        logger.radar(
            f"Radar ID {self._ID} видит от {self.tilt_cur} до {self.tilt_cur + self.tilt_per_sec} по углу наклона")
        self.pan_cur = (self.pan_cur + self.pan_per_sec) % 360
        if self.pan_cur == self.pan_start:
            self.tilt_cur = (self.tilt_cur + self.tilt_per_sec) % 180

    def changeMissileCoords(self, time: float):
        msgs_from_ccp = self._checkAvailableMessagesByType(MSG_CCP2RADAR_type)
        logger.radar(f"Radar с id {self._ID} получил {len(msgs_from_ccp)} сообщений от CombatControlPoint ")
        for msg_from_cpp in msgs_from_ccp:
            missile_id = msg_from_cpp.missile_id
            target_coord = msg_from_cpp.new_target_coord
            target_vel = msg_from_cpp.target_vel

            msg2gm = Radar2MissileMsg(time, self._ID, missile_id, target_coord, target_vel)
            self._sendMessage(msg2gm)

    def sendCcpHitMissile(self, time: float):
        msgs_from_gm = self._checkAvailableMessagesByType(MSG_GM2RADAR_type)
        if len(msgs_from_gm) != 0:
            logger.radar(
                f"Radar с id {self._ID} получил {len(msgs_from_gm)} сообщений от ЗУР о том что она перестала существовать ")
        for msg_from_gm in msgs_from_gm:
            gm_id = msg_from_gm.sender_ID
            msg2ccp = GuidedMissileHit2CCPMsg(time, self._ID, self.cp_ID, gm_id)
            self._sendMessage(msg2ccp)

    def runSimulationStep(self, time: float):
        if self.start:
            init_msg = Radar_InitMessage(time=time, sender_ID=self._ID, receiver_ID=DISPATCHER_ID)
            self._sendMessage(init_msg)
            self.start = False

        self.changeMissileCoords(time)
        self.sendCcpHitMissile(time)

        visible_objects = self.findObjects()
        msg = Radar2CombatControlMsg(time, self._ID, self.cp_ID, visible_objects)
        logger.radar(
            f"Radar с id {self._ID} отправил сообщение CombatControlPoint с id {self.cp_ID} с видимыми объектами")
        self._sendMessage(msg)

        pos_objects = [visible_objects[i][0] for i in range(len(visible_objects))]
        msg2draw = Radar2DrawerMsg(
            time=time,
            sender_ID=self._ID,
            receiver_ID=DRAWER_ID,
            pos_objects=pos_objects
        )

        logger.radar(
            f"Radad с id {self._ID} отправил сообщение Drawer с id {TARGET_TYPE_DRAWER} с положениями видимых объектов")
        self._sendMessage(msg2draw)

        msg2view = Radar_ViewMessage(time=time,
                                     sender_ID=self._ID,
                                     receiver_ID=DISPATCHER_ID,
                                     pos_objects=pos_objects)
        logger.radar(
            f"Radad с id {self._ID} отправил сообщение Dispatcher с id {DISPATCHER_ID} с положениями видимых объектов")
        self._sendMessage(msg2view)

        self.moveToNextSector()

    def changeSectorPerSec(self, new_pan_sec: float, new_tilt_sec: float):
        self.pan_per_sec = new_pan_sec
        self.tilt_per_sec = new_tilt_sec


class RadarSector(RadarRound):
    def __init__(self, dispatcher, ID: int, cp_ID: int, aero_env: AeroEnv,
                 pos, pan_start, tilt_start, dist, pan_angle, tilt_angle, pan_per_sec, tilt_per_sec, type_of_view="horizontal"):
        """ Класс, описывающий работу РЛС секторного обзора, является дочерним классом от РЛС кругового обзора:
         :param pan_angle: максимальный угол раскрыва по азимуту
         :param tilt_angle: максимальный угол раскрыва по углу наклона
         :param type_of_view: horizontal - соответствует рисунку а) для секторного РЛС,
                              vertical - соответствует рисунку б) для секторного РЛС
                              (см. README.md)"""
        super().__init__(dispatcher, ID, cp_ID, aero_env, pos, pan_start, tilt_start, dist, pan_per_sec, tilt_per_sec)
        self.pan_angle = pan_angle
        self.tilt_angle = tilt_angle
        self.type = type_of_view

    def moveToNextSector(self):
        if self.type == "horizontal":
            self.pan_cur = (self.pan_cur + self.pan_per_sec) % 360
            if self.pan_cur == (self.pan_start + self.pan_angle) % 360:
                self.tilt_cur = (self.tilt_cur + self.tilt_per_sec) % 180
                if self.tilt_cur == (self.tilt_start + self.tilt_angle) % 180:
                    self.tilt_cur = self.tilt_start
                self.pan_cur = self.pan_start
        elif self.type == "vertical":
            self.tilt_cur = (self.tilt_cur + self.tilt_per_sec) % 180
            if self.tilt_cur == (self.tilt_start + self.tilt_angle) % 180:
                self.pan_cur = (self.pan_cur + self.pan_per_sec) % 360
                if self.pan_cur == (self.pan_start + self.pan_angle) % 360:
                    self.pan_cur = self.pan_start
                self.tilt_cur = self.tilt_start

    def changeSector(self, new_pan: float, new_tilt: float):
        self.pan_angle = new_pan
        self.tilt_angle = new_tilt
