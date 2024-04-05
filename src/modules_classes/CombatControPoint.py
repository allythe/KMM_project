import typing

import numpy as np

from config.constants import GuidedMissile_SPEED, TARGET_TYPE_DRAWER, MISSILE_TYPE_DRAWER, MSG_CCP2DRAWER_type, \
    MSG_RADAR2CCP_type, MSG_SD2CCP_MS_type, DRAWER_ID
from src.messages_classes.Messages import CombatControl2StartingDeviceMsg,CombatControl2DrawerMsg, CombatControl2RadarMsg
from src.modules_classes.Simulated import Simulated, ModelDispatcher

from src.utils.logger import logger


class CCTarget:
    def __init__(self, coord: np.array, speed_dir: np.array, speed_mod: float, upd_time: float) -> None:
        """
        :param coord: координата увиденной цели
        :param speed_dir: направление скорости
        :param speed_mod: модуль скорости
        :param upd_time: время, в которое произошло посл изменение класса
        """
        self.coord = coord
        self.speed_dir = speed_dir
        self.speed_mod = speed_mod
        self.upd_time = upd_time

    def updСoord(self, new_coord: float, time: float) -> None:
        """
        Функция для обновления координаты цели
        :param new_coord: новая координата цели
        :param time: время, когда вызвали функцию
        """
        self.coord = new_coord
        self.upd_time = time

    def updSpeedMod(self, new_speed_mod: float, time: float) -> None:
        """
        Функция для обновления модуля скорости цели
        :param new_speed_mod: новый модуль скорости цели
        :param time:  время, когда вызвали функцию
        """
        self.speed_mod = new_speed_mod
        self.upd_time = time


class CCMissile:
    def __init__(self, missile_coord, missile_id, target_coord, target_vel, time):
        self.coord = missile_coord
        self.target_coord = target_coord
        self.id = missile_id
        self.speed_mod = GuidedMissile_SPEED
        self.target_vel = target_vel
        self.upd_time = time

    def updСoord(self, new_coord: float, time: float) -> None:
        """
        Функция для обновления координаты ЗУР
        :param new_coord: новая координата ЗУР
        :param time: время, когда вызвали функцию
        """
        self.coord = new_coord
        self.upd_time = time

    def updSpeedMod(self, new_speed_mod: float, time: float) -> None:
        """
        Функция для обновления модуля скорости ЗУР
        :param new_speed_mod: новый модуль скорости ЗУР
        :param time:  время, когда вызвали функцию
        """
        self.speed_mod = new_speed_mod
        self.upd_time = time

    def updTargetCoord(self, new_target_coord: float) -> None:
        """
        Функция для обновления координаты цели, за которой летит ЗУР
        :param new_target_coord: новая координата цели ЗУР
        """
        self.target_coord = new_target_coord


class CombatControlPoint(Simulated):
    def __init__(self, dispatcher: ModelDispatcher, ID: int, starting_devices_coords: dict):
        super().__init__(dispatcher, ID, None)
        self.target_list = []
        self.missile_list = []
        self.starting_devices_coords = starting_devices_coords
        logger.combat_control(f"simulating tick = {self._simulating_tick}")

    def findMostSimilarObject(self, visible_object: list, cur_time: float) -> typing.Tuple[
        int, typing.Union[CCMissile, CCTarget]]:
        """

        :param visible_object:
        :return: 0 if it is a new target, else
        1 - old target
        2 - old missile

        """
        obj_coord = visible_object[0]

        min_diff = 10e10
        sim_obj = None
        obj_type = 0

        tick = self._simulating_tick

        for target in self.target_list:
            target_coord = target.coord
            target_speed_mod = target.speed_mod
            last_target_time = target.upd_time

            coord_dif = (np.sum((target_coord - obj_coord) ** 2)) ** 0.5

            time_went = cur_time - last_target_time
            logger.combat_control(
                f"ПБУ увидела объект с текущими координатами {obj_coord}, координаты старой цели {target_coord}, время текущее {cur_time}, "
                f"последний раз видела цель в {last_target_time}, разница ккординат {coord_dif}, скорость цели {target_speed_mod} ")
            logger.combat_control(
                f"{max(0, target_speed_mod * (time_went - tick))}, {coord_dif}, {max(0, target_speed_mod * (time_went + tick))}")
            if (coord_dif < min_diff and max(0, target_speed_mod *
                                                (time_went - tick)) <= coord_dif
                    <= max(0, target_speed_mod * (time_went + tick))):
                min_diff = coord_dif
                obj_type = 1
                sim_obj = target

        for missile in self.missile_list:
            missile_coord = missile.coord
            missile_speed_mod = missile.speed_mod
            last_missile_time = missile.upd_time
            coord_dif = (np.sum((missile_coord - obj_coord) ** 2)) ** 0.5

            time_went = cur_time - last_missile_time

            logger.combat_control(f"ПБУ увидела объект с текущими координатами {obj_coord}, координаты старой ракеты {missile_coord}, время текущее {cur_time}, "
                                  f"последний раз видела ракету в {last_missile_time}, разница ккординат {coord_dif}, скорость ракеты {missile_speed_mod} ")
            logger.combat_control(f"{max(0, missile_speed_mod * (time_went - tick))}, {coord_dif}, {max(0,missile_speed_mod * (time_went + tick))}" )
            if (coord_dif < min_diff and max(0, missile_speed_mod * (time_went - tick))
                    <= coord_dif <= max(0,
                                        missile_speed_mod * (
                                                time_went + tick))):
                min_diff = coord_dif
                obj_type = 2
                sim_obj = missile
        logger.combat_control(f"ПБУ решила что объект с координатами {obj_coord} это {obj_type}, ЗУР - 2, Цель старая - 1")
        return obj_type, sim_obj

    def runSimulationStep(self, time: float) -> None:
        """
        :param time: текущее время
        """
        msgFromRadar = self._checkAvailableMessagesByType(MSG_RADAR2CCP_type)

        list_for_drawer = []

        msgsFromStartingDevice = self._checkAvailableMessagesByType(MSG_SD2CCP_MS_type)

        logger.combat_control(f"ПБУ получил от ПУ {len(msgsFromStartingDevice)} сообщений")
        if len(msgsFromStartingDevice) > 0:
            if not isinstance(msgsFromStartingDevice, list):
                msgsFromStartingDevice = [msgsFromStartingDevice]

            # дальше надо соотнести id ЗУР, координаты ЗУР и координаты их Целей
            for msgFromStartingDevice in msgsFromStartingDevice:
                missile_id = msgFromStartingDevice.id_missile
                startingDevice_id = msgFromStartingDevice.sender_ID
                missile_coord = self.starting_devices_coords[startingDevice_id]

                target_num_list = msgFromStartingDevice.order

                target_coord = self.target_list[target_num_list].coord
                target_vel = self.target_list[target_num_list].speed_dir
                self.missile_list.append(CCMissile(missile_coord, missile_id,
                                                   target_coord, target_vel, time))
                logger.combat_control(
                    f"ПБУ получил от ПУ id ЗУР:{missile_id}, начальные координаты ЗУР:{missile_coord}")
                # коорд зур, коорд ее цели, id зур, скорость зур

        if len(msgFromRadar) == 0 or len(msgFromRadar[0].visible_objects) == 0:
            return

        radar_id = msgFromRadar[0].sender_ID
        logger.combat_control(f"ПБУ получил от МФР {len(msgFromRadar[0].visible_objects)} объектов")

        if len(self.target_list) == 0:  # начало программы, когда на поле только цели
            logger.combat_control(f"ПБУ увидел свои первые объекты")

            for msg in msgFromRadar:
                visible_objects = msg.visible_objects
                for visible_object in visible_objects:
                    coord = visible_object[0]
                    speed_direct = visible_object[1]
                    speed_mod = visible_object[2]

                    self.target_list.append(CCTarget(coord, speed_direct, speed_mod, time))
                    # положить в память новые цели
                    # FIXME id of ПУ is not 2000
                    msg2StartingDevice = CombatControl2StartingDeviceMsg(time,
                                                                         self._ID, 2000, len(self.target_list) - 1,
                                                                         coord)
                    list_for_drawer.append([TARGET_TYPE_DRAWER, coord])

                    logger.combat_control(f"ПБУ отправил ПУ координаты новой цели: {coord}")
                    self._sendMessage(msg2StartingDevice)  # сказала ПУ, что нужно запустить
                    # ЗУР по координатам coord
        else:

            # получить id  ЗУР, которые ПУ отправила

            # отделить новые цели от всего что было раньше
            for msg in msgFromRadar:
                visible_objects = msg.visible_objects
                for visible_object in visible_objects:
                    obj_coord = visible_object[0]
                    obj_speed_direct = visible_object[1]
                    obj_speed_mod = visible_object[2]

                    obj_type, sim_obj = self.findMostSimilarObject(visible_object, time)
                    if obj_type == 0:
                        self.target_list.append(CCTarget(obj_coord, obj_speed_direct, obj_speed_mod, time))
                        # положить в память новые цели
                        # FIXME id of ПУ is not 2000
                        msg2StartingDevice = CombatControl2StartingDeviceMsg(time,
                                                                             self._ID, 2000, len(self.target_list) - 1,
                                                                             obj_coord)

                        logger.combat_control(f"ПБУ отправил ПУ координаты новой цели: {obj_coord}")
                        self._sendMessage(msg2StartingDevice)  # сказала ПУ, что нужно запустить
                        list_for_drawer.append([TARGET_TYPE_DRAWER, obj_coord])

                        # ЗУР по координатам coord

                    elif obj_type == 1:  # старая цель, надо обновить данные о ней в листах
                        # target list и missiles list и после этого ЗУР, которая летит за ней,
                        # перенаправить
                        idx = self.target_list.index(sim_obj)
                        list_for_drawer.append([TARGET_TYPE_DRAWER, obj_coord])

                        old_target_coord = self.target_list[idx].coord

                        self.target_list[idx].updСoord(obj_coord, time)
                        self.target_list[idx].updSpeedMod(obj_speed_mod, time)

                        for i in range(len(self.missile_list)):
                            missile = self.missile_list[i]

                            if (missile.target_coord == old_target_coord).all():
                                self.missile_list[i].updTargetCoord(obj_coord)

                                missile_id = self.missile_list[i].id
                                target_vel = self.missile_list[i].target_vel
                                msg2radar = CombatControl2RadarMsg(time, self._ID, radar_id, obj_coord, target_vel,  missile_id)
                                self._sendMessage(msg2radar)

                                logger.combat_control(
                                    f"ПБУ отправил сообщение Радару, что у ЗУР с id:{missile_id}, новые координаты ее цели:{obj_coord}")
                                break

                    elif obj_type == 2:  # старая ЗУР, нужно обновить поля в листе ЗУР
                        list_for_drawer.append([MISSILE_TYPE_DRAWER, obj_coord])

                        idx = self.missile_list.index(sim_obj)
                        logger.combat_control(
                            f"ПБУ увидел старую ЗУР с id:{self.missile_list[idx].id}, новые координаты:{obj_coord}")

                        self.missile_list[idx].updСoord(obj_coord, time)
                        self.missile_list[idx].updSpeedMod(obj_speed_mod, time)

        msg2drawer = CombatControl2DrawerMsg(
            time=time,
            sender_ID=self._ID,
            receiver_ID=DRAWER_ID,
            coordinates=list_for_drawer,
        )
        self._sendMessage(msg2drawer)