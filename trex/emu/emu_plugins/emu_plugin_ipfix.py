from trex.emu.api import *
from trex.emu.emu_plugins.emu_plugin_base import *
from trex.emu.trex_emu_validator import EMUValidator
import trex.utils.parsing_opts as parsing_opts
from trex.emu.trex_emu_ipfix_generators import AVCGenerators
from trex.emu.trex_emu_ipfix_profile import *
from trex.emu.trex_emu_ipfix_json_config import *

DEBUG = False

class IPFIXPlugin(EMUPluginBase):
    """
        Defines a Netflow/IPFIX plugin according of `Netflow v9 - RFC 3954 <https://tools.ietf.org/html/rfc3954>`_  or 
        `Netflow v10 (IPFix) - RFC 7011 <https://tools.ietf.org/html/rfc7011>`_ 
    """

    plugin_name = 'IPFIX'

    # init json examples for SDK
    INIT_JSON_NS = None
    """
    There is currently no NS init json for IPFix.
    """

    INIT_JSON_CLIENT = { 'ipfix': "Pointer to INIT_JSON_CLIENT below" }
    """
    `IPFix INIT_JSON_CLIENT:  <https://trex-tgn.cisco.com/trex/doc/trex_emu.html#_netflow_plugin>`_ 

    :parameters:

        netflow_version: uint16
            Netflow version. Might be 9 or 10, notice version 9 doesn't support variable length fields or per enterprise fields. Defaults to 10.

        dst: string
            The destination address. It is a string of the format host:port, where host can be an Ipv4 or an Ipv6 while the port should be a valid
            transport port. Example are '127.0.0.1:8080', '[2001:db8::1]:4739'

        domain_id: uint32
            The observation domain ID as defined in IPFix. If not provided, it will be randomly generated.

        generators: list
            List of generators, where each generator is a dictionary.

    :generators:

        name: string
            Name of the generator. This field is required.

        auto_start: bool
            If true will automatically start sending IPFix packets upon creation.

        template_rate_pps: float32
            Rate of IPFix template packets (in pps), defaults to 1.

        rate_pps: float32
            Rate of IPFix data packets (in pps), defaults to 3.

        data_records_num: uint32
            Number of data records in each data packet. If not provided, it will default to the maximum number of data packets which doesn't
            exceed the MTU.

        template_id: uint16
            The template ID for this generator. Must be greater than 255. This field is required. Each generator must have a unique template identifier.

        is_options_template: bool
            Indicates if this is generator will send Options Template (True) packets or Data Template packets (False). Defaults to False.

        scope_count: uint16
            Scope count in case of Options Template packets. Must be bigger than 0.

        fields: list
            List of fields for this generator. Fields are very much alike the fields of Netflow. Each field is represented by a dictionary.

        engines: list
            List of engines for this generator. Each engine is represented by a dictionary.

    :fields:

        name: string
            Name of this field. The name is required.

        type: uint16
            A uint16 that is unique per type. One can consult the RFC for specific values of types.

        length: uint16
            Length of this field in bytes. If the value is 0xFFFF, this indicates variable length fields. Variable length fields are not supported
            at the moment. Variable lengths are supported only in V10.

        enterprise_number: uint32
            Enterprise number in case the field is specific per enterprise and the type's MSB equals 1 to indicate this is an enterprise field.
            Enterprise fields are supported only in V10.

        data: [`length`]bytes
            List of bytes of size length. This will be the initial data in data packets and can be modified by the engines.

    :engines:
    
        engine_name: string
            Name of the engine. Must be the name of one of the fields.

        engine_type: string
            Type of engine, can be {uint, histogram_uint, histogram_uint_range, histogram_uint_list, histogram_uint64, histogram_uint64_range, histogram_uint64_list}

        params: dictionary
            Dictionary of params for the engine. Each engine type has different params. Explore the EMU documentation `engine section <https://trex-tgn.cisco.com/trex/doc/trex_emu.html#_engines>`_
            for more information on engines.
    """


    def __init__(self, emu_client):
        """
        Initialize an IPFixPlugin.

            :parameters:
                emu_client: :class:`trex.emu.trex_emu_client.EMUClient`
                    Valid EMU client.
        """
        super(IPFIXPlugin, self).__init__(emu_client, ns_cnt_rpc_cmd='ipfix_ns_cnt', client_cnt_rpc_cmd='ipfix_c_cnt')

    # API methods
    @client_api('getter', True)
    @update_docstring(EMUPluginBase._get_client_counters.__doc__.replace("$PLUGIN_NAME", plugin_name))
    def get_counters(self, c_key, cnt_filter=None, zero=True, verbose=True):
        return self._get_client_counters(c_key, cnt_filter, zero, verbose)

    @client_api('command', True)
    @update_docstring(EMUPluginBase._clear_client_counters.__doc__.replace("$PLUGIN_NAME", plugin_name))
    def clear_counters(self, c_key):
        return self._clear_client_counters(c_key)

    @client_api('getter', True)
    def get_gen_info(self, c_key):
        """
            Gets information about all the generators of a client.

            :parameters:

                c_key: :class:`trex.emu.trex_emu_profile.EMUClientKey`
                    EMUClientKey

            :returns: list of dictionaries

                    For each generator we get a key value mapping of name with the following parameters:

                    { 'enabled': bool
                        Flag indicating if generator is enabled.

                    'options_template': bool
                        Flag indicating if we are sending options templates for this generator or data templates.

                    'scope_count': uint16
                        Scope count in case of options template, otherwise will be 0.

                    'template_rate_pps': float32
                        The rate of template packets in pps.

                    'data_rate_pps': float32
                        The rate of data packets in pps.

                    'data_records_num': float32
                        The number of data records in a packet as user specified.

                    'data_records_num_send': float32
                        The actual number of data records in a packet as TRex calculated. For example, if user provided 0,
                        then TRex calculates the maximum number based on the MTU.

                    'fields_num': int
                        Number of fields in this generator.

                    'engines_num': int
                        Number of engines in this generator.}
        """
        ver_args = [{'name': 'c_key', 'arg': c_key, 't': EMUClientKey}]
        EMUValidator.verify(ver_args)
        res = self.emu_c._send_plugin_cmd_to_client('ipfix_c_get_gens_info', c_key)
        return res.get('generators_info', {})

    @client_api('command', True)
    def set_gen_rate(self, c_key, gen_name, template_rate, rate):
        """
            Set a new rate of data packets for an IPFix generator.

            :parameters:

                c_key: :class:`trex.emu.trex_emu_profile.EMUClientKey`
                    EMUClientKey

                gen_name: string
                    The name of the generator we are trying to alter.

                template_rate: float32
                    New rate for template packets, in pps.

                rate: float32
                    New rate for data packets, in pps.

            :returns:
               bool : Flag indicating the result of the operation.
        """
        ver_args = [{'name': 'c_key', 'arg': c_key, 't': EMUClientKey},
                    {'name': 'gen_name', 'arg': gen_name, 't': str},
                    {'name': 'template_rate', 'arg': template_rate, 't': float},
                    {'name': 'rate', 'arg': rate, 't': float}]
        EMUValidator.verify(ver_args)
        return self.emu_c._send_plugin_cmd_to_client('ipfix_c_set_gen_state', c_key=c_key, gen_name=gen_name, template_rate=template_rate, rate=rate)

    @client_api('command', True)
    def enable_generator(self, c_key, gen_name, enable):
        """
            Enable/disable an IPFix generator.

            :parameters:

                c_key: :class:`trex.emu.trex_emu_profile.EMUClientKey`
                    EMUClientKey

                gen_name: string
                    The name of the generator to alter.

                enable: bool
                    True if we wish to enable the generator, False if we wish to disable it.

            :returns:
               bool : Flag indicating the result of the operation.
        """
        ver_args = [{'name': 'c_key', 'arg': c_key, 't': EMUClientKey},
                    {'name': 'gen_name', 'arg': gen_name, 't': str},
                    {'name': 'enable', 'arg': enable, 't': bool}]
        EMUValidator.verify(ver_args)
        return self.emu_c._send_plugin_cmd_to_client('ipfix_c_set_gen_state', c_key=c_key, gen_name=gen_name, enable=enable)

    @client_api('command', True)
    def enable_ipfix(self, c_key, enable):
        """
            Enable/disable IPFix plugin for a client.
            It enable/disable all generators and the exporter. 

            :parameters:

                c_key: :class:`trex.emu.trex_emu_profile.EMUClientKey`
                    EMUClientKey

                enable: bool
                    True if we wish to enable ipfix for the client, False if we wish to disable it.

            :returns:
               bool : Flag indicating the result of the operation.
        """
        ver_args = [{'name': 'c_key', 'arg': c_key, 't': EMUClientKey},
                    {'name': 'enable', 'arg': enable, 't': bool}]
        EMUValidator.verify(ver_args)
        return self.emu_c._send_plugin_cmd_to_client('ipfix_c_set_state', c_key=c_key, enable=enable)

    # Plugins methods
    @plugin_api('ipfix_show_counters', 'emu')
    def ipfix_show_counters_line(self, line):
        """Show IPFix data counters data\n"""
        parser = parsing_opts.gen_parser(self,
                                        "show_counters_ipfix",
                                        self.ipfix_show_counters_line.__doc__,
                                        parsing_opts.EMU_SHOW_CNT_GROUP,
                                        parsing_opts.EMU_NS_GROUP,
                                        parsing_opts.MAC_ADDRESS,
                                        parsing_opts.EMU_DUMPS_OPT
                                        )

        opts = parser.parse_args(line.split())
        self.emu_c._base_show_counters(self.client_data_cnt, opts, req_ns = True)
        return True

    @plugin_api('ipfix_show_ns_counters', 'emu')
    def ipfix_show_ns_counters_line(self, line):
        '''Show IPFix namespace counters.\n'''
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_show_ns_counters_line",
                                        self.ipfix_show_ns_counters_line.__doc__,
                                        parsing_opts.EMU_SHOW_CNT_GROUP,
                                        parsing_opts.EMU_ALL_NS,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.EMU_DUMPS_OPT
                                        )

        opts = parser.parse_args(line.split())
        self.emu_c._base_show_counters(self.ns_data_cnt, opts, req_ns = True)
        return True

    @plugin_api('ipfix_get_gen_info', 'emu')
    def ipfix_get_gen_info_line(self, line):
        """Get IPFix generators information\n"""
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_get_gens_info",
                                        self.ipfix_get_gen_info_line.__doc__,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.MAC_ADDRESS,
                                        parsing_opts.EMU_DUMPS_OPT,
                                        )

        opts = parser.parse_args(line.split())
        self._validate_port(opts)
        ns_key = EMUNamespaceKey(opts.port, opts.vlan, opts.tpid)
        c_key = EMUClientKey(ns_key, opts.mac)
        res = self.get_gen_info(c_key)

        if opts.json or opts.yaml:
            dump_json_yaml(data = res, to_json = opts.json, to_yaml = opts.yaml)
            return
    
        keys_to_headers = [ {'key': 'name',                     'header': 'Name'},
                            {'key': 'template_id',              'header': 'Temp. ID'},
                            {'key': 'enabled',                  'header': 'Enabled'},
                            {'key': 'options_template',         'header': 'Opt. Temp.'},
                            {'key': 'scope_count',              'header': 'Scope cnt'},
                            {'key': 'template_rate_pps',        'header': 'Temp. Rate'},
                            {'key': 'data_rate_pps',            'header': 'Data Rate'},
                            {'key': 'data_records_num',         'header': '# Records spec.'},
                            {'key': 'data_records_num_send',    'header': '# Records calc.'},
                            {'key': 'fields_num',               'header': '# Fields'},
                            {'key': 'engines_num',              'header': '# Engines'},
        ]

        for gen_name, gen_info in res.items():
            gen_info['name'] = gen_name
        self.print_table_by_keys(list(res.values()), keys_to_headers, title="Generators")

    @plugin_api('ipfix_enable_gen', 'emu')
    def ipfix_enable_gen_line(self, line):
        """Enable an IPFix generator\n"""
        res = self._enable_disable_gen_line(line, self.ipfix_enable_gen_line, "enable")
        self.logger.post_cmd(res)

    @plugin_api('ipfix_disable_gen', 'emu')
    def ipfix_disable_gen_line(self, line):
        """Disable an IPFix generator\n"""
        res = self._enable_disable_gen_line(line, self.ipfix_enable_gen_line, "disable")
        self.logger.post_cmd(res)

    def _enable_disable_gen_line(self, line, caller_func, enable_disable):
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_enable_gen",
                                        caller_func.__doc__,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.MAC_ADDRESS,
                                        parsing_opts.IPFIX_GEN_NAME,
                                        )

        opts = parser.parse_args(line.split())
        self._validate_port(opts)
        ns_key = EMUNamespaceKey(opts.port, opts.vlan, opts.tpid)
        c_key = EMUClientKey(ns_key, opts.mac)
        return self.enable_generator(c_key, opts.gen_name, enable_disable == 'enable')

    @plugin_api('ipfix_enable', 'emu')
    def ipfix_enable_line(self, line):
        """Enable IPFix plugin for a client\n"""
        res = self._enable_disable_line(line, self.ipfix_enable_line, "enable")
        self.logger.post_cmd(res)

    @plugin_api('ipfix_disable', 'emu')
    def ipfix_disable_line(self, line):
        """Disable IPFix plugin for a client\n"""
        res = self._enable_disable_line(line, self.ipfix_enable_line, "disable")
        self.logger.post_cmd(res)

    def _enable_disable_line(self, line, caller_func, enable_disable):
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_enable",
                                        caller_func.__doc__,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.MAC_ADDRESS,
                                        )

        opts = parser.parse_args(line.split())
        self._validate_port(opts)
        ns_key = EMUNamespaceKey(opts.port, opts.vlan, opts.tpid)
        c_key = EMUClientKey(ns_key, opts.mac)
        return self.enable_ipfix(c_key, enable_disable == 'enable')

    @plugin_api('ipfix_set_data_rate', 'emu')
    def ipfix_set_data_rate_line(self, line):
        """Set IPFix generator data rate\n"""
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_set_data_rate",
                                        self.ipfix_set_data_rate_line.__doc__,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.MAC_ADDRESS,
                                        parsing_opts.IPFIX_GEN_NAME,
                                        parsing_opts.IPFIX_GEN_RATE,
                                        )

        opts = parser.parse_args(line.split())
        self._validate_port(opts)
        ns_key = EMUNamespaceKey(opts.port, opts.vlan, opts.tpid)
        c_key = EMUClientKey(ns_key, opts.mac)
        return self.set_gen_rate(c_key, opts.gen_name, template_rate=0.0, rate=opts.target_rate) # template_rate 0 will keep the template rate unchanged.

    @plugin_api('ipfix_set_template_rate', 'emu')
    def ipfix_set_template_rate_line(self, line):
        """Set IPFix generator template rate\n"""
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_set_template_rate",
                                        self.ipfix_set_template_rate_line.__doc__,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.MAC_ADDRESS,
                                        parsing_opts.IPFIX_GEN_NAME,
                                        parsing_opts.IPFIX_GEN_RATE,
                                        )

        opts = parser.parse_args(line.split())
        self._validate_port(opts)
        ns_key = EMUNamespaceKey(opts.port, opts.vlan, opts.tpid)
        c_key = EMUClientKey(ns_key, opts.mac)
        return self.set_gen_rate(c_key, opts.gen_name, template_rate=opts.target_rate, rate=0.0), # rate 0 will keep the data rate unchanged


    @client_api('getter', True)
    def get_exporter_info(self, c_key):
        """
            Gets information about the exporter used by the client.

            :parameters:

                c_key: :class:`trex.emu.trex_emu_profile.EMUClientKey`
                    EMUClientKey

            :returns: A json dictionary with the following fields:

                'exporter_type': string
                    Exporter type - emu-udp, udp, http, file

                'files': list
                    Only for HTTP exporter - contains a list of objects reporting the status of the most recent (up to 30)
                    file export sessions.

                { 'name': string
                     Name of the exported file

                'time': bool
                    The time when the file was exported

                'status': string
                    Final status of the export session

                'transport_status': string
                    Transport status of the export session

                'http_status_code': string
                    HTTP status code received from the server (collector)

                'http_response_msg': string
                    HTTP response message received from the server (collector)

                'bytes_uploaded': int
                    Number of bytes successfully uploaded by the file

                'temp_records_uploaded': int
                    Number of template records successfully uploaded by the file

                'data_records_uploaded': int
                    Number of data records successfully uploaded by the file}
        """
        ver_args = [{'name': 'c_key', 'arg': c_key, 't': EMUClientKey}]
        EMUValidator.verify(ver_args)
        res = self.emu_c._send_plugin_cmd_to_client('ipfix_c_get_exp_info', c_key)
        return res

    @plugin_api('ipfix_get_exp_info', 'emu')
    def ipfix_get_exporter_info_line(self, line):
        """Get IPFix exporter information\n"""
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_get_exp_info",
                                        self.ipfix_get_exporter_info_line.__doc__,
                                        parsing_opts.EMU_NS_GROUP_NOT_REQ,
                                        parsing_opts.MAC_ADDRESS,
                                        parsing_opts.EMU_DUMPS_OPT)

        opts = parser.parse_args(line.split())
        self._validate_port(opts)
        ns_key = EMUNamespaceKey(opts.port, opts.vlan, opts.tpid)
        c_key = EMUClientKey(ns_key, opts.mac)
        
        res = self.get_exporter_info(c_key)

        if opts.json or opts.yaml:
            dump_json_yaml(data = res, to_json = opts.json, to_yaml = opts.yaml)
            return

        keys_to_headers = [ {'key': 'name',                  'header': 'Name'},
                            {'key': 'time',                  'header': 'Time'},
                            {'key': 'status',                'header': 'Status'},
                            {'key': 'transport_status',      'header': 'Trans Status'},
                            {'key': 'http_status_code',      'header': 'HTTP Status'},
                            {'key': 'http_response_msg',     'header': 'HTTP Response Message'},
                            {'key': 'bytes_uploaded',        'header': 'Bytes Uploaded'},
                            {'key': 'temp_records_uploaded', 'header': 'Temp Records Uploaded'},
                            {'key': 'data_records_uploaded', 'header': 'Data Records Uploaded'},
        ]

        print("Exporter type: ", res['exporter_type'])
        print("\n")
        
        if 'files' in res:
            self.print_table_by_keys(list(res['files']), keys_to_headers, title = "Files Info")

    @plugin_api('ipfix_push', 'emu')
    def ipfix_push(self, line):
        """Pushing IPFIX files to destination URL using HTTP or UDP. To stop, use 'emu_remove_profile'.\n"""
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_push",
                                        self.ipfix_push.__doc__,
                                        parsing_opts.IPFIX_DST_URL,
                                        parsing_opts.IPFIX_DIR,
                                        parsing_opts.IPFIX_DIR_SCANS_NUM,
                                        parsing_opts.IPFIX_FILES_WAIT_TIME,
                                        parsing_opts.IPFIX_FILES_WAIT_TIME_SPEEDUP,
                                        parsing_opts.IPFIX_HTTP_REPEATS_NUM,
                                        parsing_opts.IPFIX_HTTP_REPEATS_WAIT_TIME,
                                        parsing_opts.IPFIX_HTTP_SITES_PER_TENANT,
                                        parsing_opts.IPFIX_HTTP_DEVICES_PER_SITE,
                                        parsing_opts.IPFIX_HTTP_HEADER_FIELDS_JSON_FILE,
                                        parsing_opts.IPFIX_UDP_PACKETS_WAIT_TIME,
                                        )
        opts = parser.parse_args(line.split())

        exporter_params = IpfixExporterParamsFactory().create_obj_from_dst_url(opts.dst_url)
        if exporter_params is None:
            raise TRexError("Failed to create ipfix exporter")

        header_fields_json = None

        if opts.header_fields_json_file:
            try:
                with open(opts.header_fields_json_file, 'r') as file:
                    header_fields_json = file.read()
            except FileNotFoundError:
                raise TRexError("Header fields JSON file doesn't exist")

        exporter_params.set_export_from_dir(True)
        if exporter_params.get_type() == "http":
            exporter_params.set_repeats_num(opts.http_repeats_num)
            exporter_params.set_repeats_wait_time(opts.http_repeats_wait_time)
            exporter_params.set_export_from_dir_params(dir = opts.dir,
                                                       dir_scans_num = opts.dir_scans_num,
                                                       files_wait_time = opts.files_wait_time,
                                                       files_wait_time_speedup = opts.files_wait_time_speedup)
            exporter_params.set_header_fields(header_fields_json)

        if exporter_params.get_type() == "udp":
            exporter_params.set_export_from_dir_params(dir = opts.dir,
                                                       dir_scans_num = opts.dir_scans_num,
                                                       files_wait_time = opts.files_wait_time,
                                                       files_wait_time_speedup = opts.files_wait_time_speedup,
                                                       packets_wait_time = opts.udp_packets_wait_time)

        generators = AVCGenerators(["Dummy"])
        ipfix_plugin = IpfixPlugin(exporter_params, generators)
        ipfix_plugin.set_domain_id(270) 

        profile = IpfixDevicesAutoTriggerProfile(ipfix_plugin=ipfix_plugin,
                                                 device_mac = "00:00:00:00:00:01",
                                                 device_ipv4 = "1.1.1.1",
                                                 sites_per_tenant = opts.http_sites_per_tenant,
                                                 devices_per_site = opts.http_devices_per_site)

        if DEBUG:
            print(profile.dump_json())

        self.emu_c.remove_profile()
        self.emu_c.load_profile(profile.get_profile())

    @plugin_api('ipfix_load_profile_cfg', 'emu')
    def ipfix_load_profile_from_cfg_file(self, line):
        """Create an IPFIX profile based on a JSON config file.\n"""
        parser = parsing_opts.gen_parser(self,
                                        "ipfix_load_profile_from_cfg_file",
                                        self.ipfix_load_profile_from_cfg_file.__doc__,
                                        parsing_opts.IPFIX_PROFILE_CFG_FILE,
                                        )
        opts = parser.parse_args(line.split())

        try:
            config = IpfixProfileJsonConfig(opts.profile_cfg_file)
            profile = config.get_profile()
        except ValueError as error:
            print("Failed to create profile from config file, err:", error)
            return

        if DEBUG:
            print(config.dump_profile_json())

        self.emu_c.remove_profile()
        self.emu_c.load_profile(profile)
