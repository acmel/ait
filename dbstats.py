#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

try:
	from sqlite3 import connect as sqlite3_connect
except:
	from sqlite import connect as sqlite3_connect

import os, socket, hashlib

def dbutil_create_text_table_query(table, columns):
	query = "create table %s (%s)" % (table,
					  reduce(lambda a, b: a + ", %s" % b,
					   	 map(lambda a: "%s %s" % a,
						     columns)))
	return query

def dbutils_get_columns(cursor, table):
	cursor.execute('select * from %s where rowid = 1' % table)
	columns = [column[0] for column in cursor.description]
	columns.sort()
	return columns

def dbutils_add_missing_text_columns(cursor, table, old_columns, columns):
	for column in columns:
		if column[0] not in old_columns:
			cursor.execute("alter table %s add column %s %s" % (table,
									    column[0],
									    column[1]))

def get_sysinfo_dict(system):
	result = {}
	f = file(system + ".sysinfo")
	for line in f.readlines():
		line = line.strip()
		if len(line) == 0 or line[0] == "#":
			continue
		# Make sure we cope with the separator being in the field value
		# Ex.: "foo: bar:baz"
		# Should produce result["foo"] = "bar:baz"
		sep = line.index(":")
		key = line[:sep]
		value = line[sep + 1:].strip()
		if key.startswith("nic."):
			if not result.has_key("nics"):
				result["nics"] = {}

			key = key[4:]
			sep = key.index(".")
			nic = key[:sep]
			nic_key = key[sep + 1:]
			if not result["nics"].has_key(nic):
				result["nics"][nic] = {}
				result["nics"][nic]["name"] = nic

			result["nics"][nic][nic_key] = value
		else:
			result[key] = value
	f.close()
	return result

def nic_tunings_keys(nics):
	keys = []
	for nic in nics.keys():
		keys += nics[nic].keys()
	keys = list(set(keys))
	return keys

class dbstats:
	def __init__(self, appname):
		self.conn = sqlite3_connect("%s.db" % appname)
		self.cursor = self.conn.cursor()

		self.create_tables()

	system_tunings_columns = [ ( "softirq_net_tx_prio", "text" ),
				   ( "softirq_net_rx_prio", "text" ),
				   ( "app_rtprio", "text" ),
				   ( "irqbalance", "text" ),
				   ( "app_affinity", "text" ),
				   ( "app_sched", "text" ),
				   ( "kcmd_isolcpus", "text" ),
				   ( "oprofile", "text" ),
				   ( "systemtap", "text" ),
				   ( "kcmd_maxcpus", "text" ),
				   ( "vsyscall64", "text" ),
				   ( "futex_performance_hack", "text" ),
				   ( "kcmd_idle", "text" ),
				   ( "lock_stat", "text" ),
				   ( "tcp_congestion_control", "text" ),
				   ( "tcp_sack", "text" ),
				   ( "tcp_dsack", "text" ),
				   ( "tcp_window_scaling", "text" ),
				   ( "kcmd_nohz", "text" ),
				   ( "clocksource", "text" ),
				   ( "glibc_priv_futex", "text" ),
				   ( "sched_min_granularity_ns", "text" ),
				   ( "loadavg", "text" ) ]

	def create_tables(self):
		query = dbutil_create_text_table_query("system_tunings", self.system_tunings_columns)
		try:
			self.cursor.execute(query)
		except:
			old_tunings_columns = dbutils_get_columns(self.cursor, "system_tunings")
			if [ a[0] for a in self.system_tunings_columns ] != old_tunings_columns:
				dbutils_add_missing_text_columns(self.cursor,
								 "system_tunings",
								 old_tunings_columns,
								 self.system_tunings_columns)
		try:
			self.cursor.execute('''
				create table machine_hardware (arch text, vendor text,
							       cpu_model text, nr_cpus int)
			''')
		except:
			pass

		try:
			self.cursor.execute('''
				create table nic_hardware (driver text,
							   version text,
							   firmware_version text)
			''')
		except:
			pass

		try:
			self.cursor.execute('''
				create table nic (name text, hw int, bus_info text, tunings int)
			''')
		except:
			pass

		try:
			self.cursor.execute('''
				create table machine (nodename text, hw int)
			''')
		except:
			pass

		software_versions_columns = [ ( "kernel_release", "text" ),
					      ( "libc", "text" ) ]
		query = dbutil_create_text_table_query("software_versions",
						       software_versions_columns)
		try:
			self.cursor.execute(query)
		except:
			old_software_versions_columns = dbutils_get_columns(self.cursor, "software_versions")
			if [ a[0] for a in software_versions_columns ] != old_software_versions_columns:
				dbutils_add_missing_text_columns(self.cursor,
								 "software_versions",
								 old_software_versions_columns,
								 software_versions_columns)

		try:
			self.cursor.execute('''
				create table environment (machine int,
							  nic int,
							  system_tunings int,
							  software_versions int)
			''')
		except:
			pass

		# FIXME rename 'env' to 'server_env'
		try:
			self.cursor.execute('''
				create table report (env int,
						     client_env int,
						     ctime int,
						     filename text,
						     comment int)
			''')
		except:
			pass

		for metric in [ "avg", "min", "max", "dev" ]:
			try:
				self.cursor.execute('''
					create table latency_per_rate_%s (report int,
									  rate int,
									  value real)
				''' % metric)
			except:
				pass

		try:
			self.cursor.execute('''
				create table comment (comment text)
			''')
		except:
			pass

		try:
			self.cursor.execute('''
				create table netperf_udp_stream (report int,
								 msg_size int,
								 msg_err int,
								 local_socket_size int,
								 local_elapsed_time real,
								 local_msg_ok int,
								 local_throughput real, 
								 remote_socket_size int,
								 remote_elapsed_time real,
								 remote_msg_ok int,
								 remote_throughput real)
					    ''')
		except:
			pass

		self.conn.commit()

	def create_nic_tunings_table(self, columns):
		columns.append("sig")
		columns.sort()
		query = "create table nic_tunings (%s)" % reduce(lambda a, b: a + ", %s" % b,
								 map(lambda a: "%s text" % a.replace(".", "_"),
								     columns))
		print query
		try:
			self.cursor.execute(query)
		except:
			old_tunings_columns = dbutils_get_columns(self.cursor, "nic_tunings")
			if [ a[0] for a in columns ] != old_tunings_columns:
				dbutils_add_missing_text_columns(self.cursor,
								 "nic_tunings",
								 old_tunings_columns,
								 columns)

		self.conn.commit()

	def getnicbyip(self, nics, ipaddr):
		for nic in nics.keys():
			if nics[nic].has_key("ipaddr") and \
			   nics[nic]["ipaddr"] == ipaddr:
				return nic

		return None

	def get_nic_tunings_id(self, system_name, system_settings):
		if not system_settings.has_key("nics"):
			return None
		nics = system_settings["nics"]
		ipaddr = socket.gethostbyname(system_name)
		nicname = self.getnicbyip(nics, ipaddr)
		if not nicname:
			return None
		nic = nics[nicname]
		nicsig = hashlib.sha256("%s" % nic).hexdigest()
		self.cursor.execute("select rowid from nic_tunings where sig = %s" % nicsig)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def get_dict_table_id(self, table, parms):
		where_condition = reduce(lambda a, b: a + " and %s" % b,
					 map(lambda a: ('%s = "%s"' % (a, parms[a])),
					     parms.keys()))
		self.cursor.execute("select rowid from %s where %s" % (table,
								       where_condition))
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_dict_table_id(self, table, parms):
		field_list = reduce(lambda a, b: a + ", %s" % b, parms.keys())
		values_list = reduce(lambda a, b: a + ", %s" % b,
				     map(lambda a: ('"%s"' % (parms[a])),
				     	 parms.keys()))
		query = '''
			insert into %s ( %s )
				      values ( %s )
			       ''' % (table, field_list, values_list)
		self.cursor.execute(query)
		self.conn.commit()

	def get_nic_hardware_id(self, parms):
		self.cursor.execute('''
			select rowid from nic_hardware where
				driver = "%s" and
				version = "%s" and
				firmware_version = "%s"
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_nic_hardware_id(self, parms):
		self.cursor.execute('''
			insert into nic_hardware (driver, version, firmware_version)
					      values ( "%s", "%s", "%s" )
			       ''' % parms)
		self.conn.commit()

	def get_machine_hardware_id(self, parms):
		self.cursor.execute('''
			select rowid from machine_hardware where
				arch = "%s" and
				vendor = "%s" and
				cpu_model = "%s" and
				nr_cpus = %d
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_machine_hardware_id(self, parms):
		self.cursor.execute('''
			insert into machine_hardware ( arch, vendor,
						       cpu_model, nr_cpus )
					      values ( "%s", "%s", "%s", %d )
			       ''' % parms)
		self.conn.commit()

	def get_machine_id(self, parms):
		self.cursor.execute('''
			select rowid from machine
				     where nodename = "%s" and hw = %d
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_machine_id(self, parms):
		self.cursor.execute('''
			insert into machine ( nodename, hw )
				     values ("%s", %d )
			       ''' % parms)
		self.conn.commit()

	def get_env_id(self, parms):
		self.cursor.execute('''
			select rowid from environment
				     where machine = %d and
					   system_tunings = %d and
					   nic = %d and
					   nic_tunings = %d and
					   software_versions = %d
			       ''' % parms)
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_env_id(self, parms):
		self.cursor.execute('''
			insert into environment ( machine, system_tunings,
						  nic, nic_tunings,
						  software_versions )
					 values ( %d, %d, %d, %d, %d )
			       ''' % parms)
		self.conn.commit()

	def get_report_id(self, server_env, client_env, ctime, filename):
		self.cursor.execute('''
			select rowid from report where
				env = %d and
				client_env = %d and
				ctime = "%s" and
				filename = "%s"
			       ''' % (server_env, client_env, ctime, filename))
		result = self.cursor.fetchone()
		if result:
			return result[0]
		return None

	def create_report_id(self, server_env, client_env, ctime, filename):
		self.cursor.execute('''
			insert into report ( env, client_env, ctime, filename )
				    values ( %d, %d, "%s", "%s")
			       ''' % (server_env, client_env, ctime, filename))
		self.conn.commit()


	def get_max_rate_for_report(self, report):
		self.cursor.execute('''
					select max(rate)
					  from latency_per_rate_avg
					  where report = %d
				  ''' % report)
		results = self.cursor.fetchall()
		if results and results[0][0]:
			return int(results[0][0])
		return None

	def get_max_msg_size_for_report(self, report):
		self.cursor.execute('''
					select max(msg_size)
					  from netperf_udp_stream
					  where report = %d
				  ''' % report)
		results = self.cursor.fetchall()
		if results and results[0][0]:
			return int(results[0][0])
		return None

	def get_server_env_id_for_report(self, report):
		self.cursor.execute('select env from report where rowid = %d' % report)
		results = self.cursor.fetchone()
		if results:
			return int(results[0])
		return None

	def get_ctime_for_report(self, report):
		self.cursor.execute('select ctime from report where rowid = %d' % report)
		results = self.cursor.fetchone()
		if results:
			return int(results[0])
		return None

	def get_kernel_release_for_report(self, report):
		self.cursor.execute('''
					select s.kernel_release
					  from report rep,
					       environment env,
					       software_versions s
					  where rep.rowid = %d and
					  	rep.env = env.rowid and
					  	env.software_versions = s.rowid
				  ''' % report)
		results = self.cursor.fetchone()
		if results:
			return results[0]
		return None

	def get_libc_release_for_report(self, report):
		self.cursor.execute('''
					select s.libc
					  from report rep,
					       environment env,
					       software_versions s
					  where rep.rowid = %d and
					  	rep.env = env.rowid and
					  	env.software_versions = s.rowid
				  ''' % report)
		results = self.cursor.fetchone()
		if results:
			return results[0]
		return None

	def get_system_tunings_for_report(self, report):
		self.cursor.execute('''
					select r.env,
					       e.system_tunings,
					       s.kernel_release,
					       s.libc,
					       t.*
					  from report r,
					       environment e,
					       system_tunings t,
					       software_versions s
					  where r.env = e.rowid and
						e.system_tunings = t.rowid and
						e.software_versions = s.rowid and
						r.rowid = %d
				  ''' % report)
		return self.cursor.fetchone()

	def get_system_tunings_by_id(self, id):
		self.cursor.execute('''
					select *
					  from system_tunings
					  where rowid = %d
				  ''' % id)
		return self.cursor.fetchone()

	def get_system_tunings_ids_for_query(self, query):
		try:
			self.cursor.execute('''
						select rowid
						  from system_tunings
						  where %s
					  ''' % query)
			return [ id[0] for id in self.cursor.fetchall() ]
		except: 
			raise SyntaxError

	def machine_hardware_id(self, system):
		machine_hardware = (system["arch"],
				    system["vendor_id"],
				    system["cpu_model"],
				    int(system["nr_cpus"]))
		machine_hardware_id = self.get_machine_hardware_id(machine_hardware)
		if not machine_hardware_id:
			self.create_machine_hardware_id(machine_hardware)
			machine_hardware_id = self.get_machine_hardware_id(machine_hardware)

		return machine_hardware_id

	def machine_id(self, system, machine_hardware_id):
		machine = (system["nodename"], machine_hardware_id)
		machine_id = self.get_machine_id(machine)
		if not machine_id:
			self.create_machine_id(machine)
			machine_id = self.get_machine_id(machine)

		return machine_id

	def get_system_tunings_id(self, machine):
		system_tunings = {}

		# First get the tunings collected by ait-get-sysinfo.py
		for tuning in [ a[0] for a in self.system_tunings_columns ]:
			if machine.has_key(tuning):
				system_tunings[tuning] = machine[tuning]

		id = self.get_dict_table_id("system_tunings", system_tunings)
		if not id:
			self.create_dict_table_id("system_tunings", system_tunings)
			id = self.get_dict_table_id("system_tunings", system_tunings)

		return id

	def setreport(self, report, client_machine, server_machine):
		# Load the client and server hardware info from the data
		# collected by ait-get-sysinfo.py
		client_system = get_sysinfo_dict(client_machine)
		server_system = get_sysinfo_dict(server_machine)

		# Now that we have the list of nic tunings, make sure the
		# table exists
		server_nic_tunings_keys = nic_tunings_keys(server_system["nics"])
		self.create_nic_tunings_table(server_nic_tunings_keys)

		# Get the hardware ID for the client and server machines
		client_machine_hardware_id = self.machine_hardware_id(client_system)
		server_machine_hardware_id = self.machine_hardware_id(server_system)
		
		# Get the machine ID for the client and server machines
		client_machine_id = self.machine_id(client_system, client_machine_hardware_id)
		server_machine_id = self.machine_id(server_system, server_machine_hardware_id)

		# Find the server system tunings id in the DB
		system_tunings_id = self.get_system_tunings_id(server_system)

		# Find the nic tunings id in the DB
		server_nic_tunings_id = self.get_nic_tunings_id(server_machine, server_system)
		print server_nic_tunings_id
		sys.exit(1)

		# Collect the versions of relevant system components (kernel,
		# libc, etc):
		software_versions = {}
		software_versions["kernel_release"] = server_system["kernel_release"]
		if server_system.has_key("libc"):
			software_versions["libc"] = server_system["libc"]

		software_versions_id = self.get_dict_table_id("software_versions", software_versions)
		if not software_versions_id:
			self.create_dict_table_id("software_versions", software_versions)
			software_versions_id = self.get_dict_table_id("software_versions",
								      software_versions)
		
		# server_machine_id, system_tunings_id, kernel_release
		server_env_parms = (server_machine_id, system_tunings_id,
				    server_nic_id, server_nic_tunings_id, software_versions_id)
		server_env_id = self.get_env_id(server_env_parms)

		ctime = os.stat(report).st_ctime

		if server_env_id:
			self.report = self.get_report_id(server_env_id, client_machine_id, ctime, report)
			if self.report:
				return False
		else:
			self.create_env_id(server_env_parms)
			server_env_id = self.get_env_id(server_env_parms)

		self.create_report_id(server_env_id, client_machine_id, ctime, report)
		self.report = self.get_report_id(server_env_id, client_machine_id, ctime, report)
		return True

	def insert_latency_per_rate(self, metric, rates):
		for rate in rates.keys():
			self.cursor.execute('''
				insert into latency_per_rate_%s ( report, rate, value )
					     values ( %d, %d, "%f" )
				       ''' % (metric, self.report,
				       	      rate, rates[rate]))
		self.conn.commit()

	def insert_netperf_udp_stream(self, msg_size, msg_size_dict):
		query = '''
			insert into netperf_udp_stream ( report, msg_size, msg_err,
							 local_socket_size,
							 local_elapsed_time,
							 local_msg_ok,
							 local_throughput, 
							 remote_socket_size,
							 remote_elapsed_time,
							 remote_msg_ok,
							 remote_throughput)
				     values ( %d, %d, %d, %d, %f, %d, %f, %d, %f, %d, %f  )
			       ''' % (self.report, msg_size, msg_size_dict["msg_err"],
				      msg_size_dict["local_socket_size"],
				      msg_size_dict["local_elapsed_time"],
				      msg_size_dict["local_msg_ok"],
				      msg_size_dict["local_throughput"],
				      msg_size_dict["remote_socket_size"],
				      msg_size_dict["remote_elapsed_time"],
				      msg_size_dict["remote_msg_ok"],
				      msg_size_dict["remote_throughput"])
		self.cursor.execute(query)
		self.conn.commit()
