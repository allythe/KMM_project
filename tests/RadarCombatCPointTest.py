import numpy as np

from src.classes.AeroEnv import AeroEnv, Airplane
from src.classes.CombatControPoint import CombatControlPoint
from src.classes.ModelDispatcher import ModelDispatcher
from src.classes.Radar import RadarRound
from src.classes.StartingDevice import StartingDevice

if __name__ == '__main__':
    dispatcher = ModelDispatcher()
    dispatcher.setSimulatingRate(1)
    dispatcher.setSimulationTime(25)

    n = 1
    targets = [Airplane(dispatcher=dispatcher, ID=i, pos=np.array([10000, 10000, 10000]), rad=5, vel=np.array([100, 100, 100]),
                        t_start=0, t_end=25) for i in range(n)]
    env = AeroEnv(dispatcher, len(targets))
    for el in targets:
        env.addEntity(el)

    radar = RadarRound(dispatcher, 1, 3000, env, (0, 0, 0), 0, 0, 500000, 360, 180)
    start_devices = [StartingDevice(dispatcher, 2000, np.array([0, 0, 0]), env)]
    starting_devices_coords = {}
    for sd in start_devices:
        starting_devices_coords[sd._ID] = sd.pos
    combat = CombatControlPoint(dispatcher, 3000, starting_devices_coords)

    dispatcher.configurate([env, radar, combat, *start_devices])
    dispatcher.run()

    # rate, messages = dispatcher.getMessageHistory()
    # for i in range(len(messages)):
    #     print(f"time: {i/rate}")
    #
    #     for message in messages[i]:
    #         print(f"time: {i/rate} ", vars(message))
