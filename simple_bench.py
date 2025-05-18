import time
import logging
from pprint import pprint
import argparse
import sys, os

from trex.stl.api import *

logging.basicConfig(level=logging.INFO)
cur_dir = os.path.dirname(__file__)

STL_PROFILES_PATH = os.path.abspath(os.path.join(cur_dir, 'profiles'))
EXT_LIBS_PATH = os.path.join(cur_dir, 'external_libs') # client package path

print(f"profile_path: {STL_PROFILES_PATH}")
print(f"ext_libs_path: {EXT_LIBS_PATH}")

assert os.path.isdir(STL_PROFILES_PATH), 'Could not determine STL profiles path'
assert os.path.isdir(EXT_LIBS_PATH), 'Could not determine external_libs path'


class SimplePacketTest:
    def __init__(self, server: str, base_rate, target_rate: int, duration: int, steps: int):
        self.profile = STLProfile.load_py(os.path.join(STL_PROFILES_PATH, 'simple.py'))
        self.c = STLClient(server = server)
        self.base_rate = base_rate
        self.target_rate = target_rate
        self.duration = duration
        self.steps = steps
        self.c.connect()
        self.c.reset()
        self.logger = logging.getLogger("SimplePacketTest")
        self.__cur_stats = {}
        self.error_threshold = 0.1

        table = stl_map_ports(self.c)
        self.dir_0 = [x[0] for x in table['bi']]
        self.dir_1 = [x[1] for x in table['bi']]

    def __update_stats(self):
        self.__cur_stats = self.c.get_stats()

    def __calc_i_o_packets(self):
        stats = self.__cur_stats
        # sum dir 0
        dir_0_opackets = sum([stats[i]["opackets"] for i in self.dir_0])
        dir_0_ipackets = sum([stats[i]["ipackets"] for i in self.dir_0])

        # sum dir 1
        dir_1_opackets = sum([stats[i]["opackets"] for i in self.dir_1])
        dir_1_ipackets = sum([stats[i]["ipackets"] for i in self.dir_1])

        return dir_0_opackets, dir_1_opackets, dir_0_ipackets, dir_1_ipackets

    def __print_stats(self, dir_0_opackets, dir_1_opackets, lost_0, lost_1, rate):
        self.logger.info(f"Packets injected from {self.dir_0}: {dir_0_opackets:,}")
        self.logger.info(f"Packets injected from {self.dir_1}: {dir_1_opackets:,}")
        self.logger.info(f"packets lost from {self.dir_0} --> {self.dir_1}:   {lost_0:,} pkts")
        self.logger.info(f"packets lost from {self.dir_1} --> {self.dir_0}:   {lost_1:,} pkts")
        self.logger.info(f"packet rate {self.dir_0} --> {self.dir_1}:   {rate:,} pkts/s")

        if self.c.get_warnings():
            self.logger.warning("\n\n*** test had warnings ****\n\n")
            for w in self.c.get_warnings():
                self.logger.warning(w)

    def start(self):
        try:
            print(f"Mapped ports to sides {self.dir_0} <--> {self.dir_1}")
            streams = self.profile.get_streams()

            self.c.add_streams(streams, ports = self.dir_0)
            self.c.add_streams(streams, ports = self.dir_1)

            self.c.clear_stats()
            self.c.start(ports = (self.dir_0 + self.dir_1), mult='1kpps', total = True)
        except Exception as e:
            self.logger.error(f"Error: failed to start the test: {e}")
            self.c.disconnect()
            sys.exit(1)

    def update(self, new_rate):
        self.c.clear_stats()
        self.c.update(ports = (self.dir_0 + self.dir_1), mult=new_rate, total = True)

    def stop(self):
        self.c.stop()

    def __calc_stats(self, duration):
        self.__update_stats()
        dir_0_opackets, dir_1_opackets, dir_0_ipackets, dir_1_ipackets = self.__calc_i_o_packets()
        rate = (dir_0_ipackets  + dir_1_ipackets) / duration
        lost_0 = dir_0_opackets - dir_1_ipackets
        lost_1 = dir_1_opackets - dir_0_ipackets

        return dir_0_opackets, dir_1_opackets, lost_0, lost_1, rate

    def do_test(self):
        logger = logging.getLogger("SimplePacketTest::do_test")
        logger.info("Starting test")
        self.start()
        self.__update_stats()
        logger.info(f"Waiting initial ramp up time {self.duration} seconds")
        time.sleep(self.duration)
        logger.info(f"Done")
        self.__update_stats()

        step = int((self.target_rate - self.base_rate) / self.steps)
        rates = [step for step in range(self.base_rate, self.target_rate, step)]
        for target_rate in rates:
            fail = False
            try:
                logger.info(f"Updating rate to {target_rate}kpps")
                self.update(f"{target_rate}kpps")
                time.sleep(self.duration)
                logger.info(f"Done")
            except Exception as e:
                logger.error(f"Error: failed to update the rate: {e}")
                fail = True
            dir_0_opackets, dir_1_opackets, lost_0, lost_1, rate = self.__calc_stats(self.duration)
            self.__print_stats(dir_0_opackets, dir_1_opackets, lost_0, lost_1, rate)
            if fail or abs(float(target_rate) - rate / 1000) > self.error_threshold * float(target_rate):
                logger.error(
                    f"Error: difference between target rate ({target_rate}kpps) and actual rate ({rate}kpps)> {self.error_threshold * 100}%")
                break
        logger.info("Waiting for triple step duration to get the final stats")
        self.c.clear_stats()
        time.sleep(self.duration * 6)
        self.stop()
        logger.info(f"Done")
        dir_0_opackets, dir_1_opackets, lost_0, lost_1, rate = self.__calc_stats(self.duration * 6)
        self.__print_stats(dir_0_opackets, dir_1_opackets, lost_0, lost_1, rate)
        self.c.disconnect()



parser = argparse.ArgumentParser(description="Example for TRex Stateless, sending IMIX traffic")
parser.add_argument('--trex',
                    dest='trex',
                    help='Remote trex address',
                    default='127.0.0.1',
                    type = str)
parser.add_argument('-t', '--target_rate',
                    dest='target_rate',
                    help='Target packet rate in kpps',
                    type=int,
                    required=True)
parser.add_argument('-d', '--duration',
                    dest='duration',
                    help='duration of each ramp in seconds',
                    type=int,
                    default=10)
parser.add_argument('-b', '--base_rate',
                    dest='base_rate',
                    help='baseline, from which test will start, in kpps',
                    type=int,
                    default=10)
parser.add_argument('-s', '--steps',
                    dest='step',
                    help='how many steps we should do before reaching the goal',
                    type=int,
                    default=10)

args = parser.parse_args()

# run the tests
test = SimplePacketTest(args.trex, args.base_rate, args.target_rate, args.duration, args.step)
test.do_test()

