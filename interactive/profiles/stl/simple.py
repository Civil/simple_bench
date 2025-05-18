from trex_stl_lib.api import *
import argparse

class STLSimpleStateless(object):
    """
    tunables:
        size : type (int)
             - define the packet's size in the stream.
    """
    ports = {'min': 1234, 'max': 65500}
    pkt_size = {'min': 64, 'max': 9216}

    def create_stream (self, size, vm, src, dst):
        # Create base packet and pad it to size
        base_pkt = Ether()/IP(src=src, dst=dst)/UDP(sport=self.ports['min'],dport=30,chksum=0)
        pad = max(0, size - len(base_pkt) - 4) * 'x'
        pkt = STLPktBuilder(pkt=base_pkt/pad,
                            vm=vm)

        return STLStream(packet=pkt,
                         mode=STLTXCont(pps=1),
                         isg=0,
                         flow_stats=None)

    def get_streams (self, port_id, direction, tunables, **kwargs):
        parser = argparse.ArgumentParser(description='Argparser for {}'.format(os.path.basename(__file__)), 
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        parser.add_argument('--size',
                            type=int,
                            default=64,
                            help='define the packet size in the stream.')
        parser.add_argument('--cache',
                            type=int,
                            default=1024,
                            help='define how many packets to cache')
        parser.add_argument('--offset',
                            type=int,
                            default=0,
                            help='offset for the source and dst ip address')

        args = parser.parse_args(tunables)
        size, offset = args.size, args.offset
        if size < self.pkt_size['min']:
            raise argparse.ArgumentTypeError(f'packet size {size} is less than allowed minimum: {self.pkt_size["min"]}')
        if size > self.pkt_size['max']:
            raise argparse.ArgumentTypeError(f'packet size {size} is larger than allowed maximum: {self.pkt_size["max"]}')

        src, dst = f'16.0.{int(port_id/2)+offset}.1', f'48.0.{int(port_id/2)+offset}.1'

        vm_var = STLVM()

        vm_var.var(name='ip', min_value=0, max_value=255, size=1, op='random')
        vm_var.var(name='port', min_value=self.ports['min'], max_value=self.ports['max'], size=2, op='random')
        vm_var.write(fv_name='ip', pkt_offset='IP.src', offset_fixup=3)
        vm_var.write(fv_name='ip', pkt_offset='IP.dst', add_val=128, offset_fixup=3)
        vm_var.write(fv_name='port', pkt_offset='UDP.sport')
        vm_var.fix_chksum()
        vm_var.set_cached(args.cache)

        return [self.create_stream(size, vm_var, src, dst)]


# dynamic load - used for trex console or simulator
def register():
    return STLSimpleStateless()




