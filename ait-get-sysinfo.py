#! /usr/bin/python
# -*- python -*-
# -*- coding: utf-8 -*-

import ethtool, os, procfs, schedutils, sys, utilist

def get_tso_state():
	state=""
	for iface in ethtool.get_devices():
		try:
			state += "%s=%d," % (iface, ethtool.get_tso(iface))
		except:
			pass
	state = state.strip(",")
	return state

def get_ufo_state():
	state=""
	# UFO may not be present on this kernel and then we get an exception
	try:
		for iface in ethtool.get_devices():
			state += "%s=%d," % (iface, ethtool.get_ufo(iface))
	except:
		pass
	state = state.strip(",")

	return state

def get_nic_kthread_affinities(irqs):
	state=""
	for iface in ethtool.get_devices():
		irq = irqs.find_by_user(iface)
		if not irq:
			continue
		# affinity comes from /proc/irq/N/smp_affinities, that
		# needs root priviledges
		try:
			state += "%s=%s;" % (iface, utilist.csv(utilist.hexbitmask(irqs[irq]["affinity"], irqs.nr_cpus), '%x'))
		except:
			pass
	state = state.strip(";")
	return state

def get_nic_kthread_rtprios(irqs, ps):
	state=""
	for iface in ethtool.get_devices():
		irq = irqs.find_by_user(iface)
		if not irq:
			continue
		pids = ps.find_by_name("IRQ-%s" % irq)
		if not pids:
			continue
		state += "%s=%s;" % (iface, ps[pids[0]]["stat"]["rt_priority"])
	state = state.strip(";")
	return state

if __name__ == '__main__':

	app_process_name = sys.argv[1]
	sysinfo = {}

	pfs = procfs.stats()
	kcmd = procfs.cmdline()
	irqs = procfs.interrupts()
	cpuinfo = procfs.cpuinfo()
	uname = os.uname()

	# arch, vendor, cpu_model, nr_cpus
	sysinfo["nodename"] = uname[1]
	sysinfo["arch"] = uname[4]
	sysinfo["kernel_release"] = uname[2] 
	sysinfo["vendor_id"] = cpuinfo["vendor_id"]
	sysinfo["cpu_model"] = cpuinfo["model name"]
	sysinfo["nr_cpus"] = cpuinfo.nr_cpus
		
	sysinfo["tso"] = get_tso_state()
	sysinfo["ufo"] = get_ufo_state()
	sysinfo["softirq_net_tx_prio"] = pfs.get_per_cpu_rtprios("softirq-net-tx")
	sysinfo["softirq_net_rx_prio"] = pfs.get_per_cpu_rtprios("softirq-net-rx")

	sysinfo["irqbalance"] = False
	if pfs.find_by_name("irqbalance"):
		sysinfo["irqbalance"] = True

	sysinfo["oprofile"] = False
	if pfs.find_by_name("oprofiled"):
		sysinfo["oprofile"] = True

	sysinfo["systemtap"] = False
	if pfs.find_by_name("staprun"):
		sysinfo["systemtap"] = True

	if kcmd.options.has_key("kcmd_isolcpus"):
		sysinfo["kcmd_isolcpus"] = kcmd.options["kcmd_isolcpus"]
	elif kcmd.options.has_key("default_affinity"):
		sysinfo["kcmd_isolcpus"] = "da:%s" % kcmd.options["default_affinity"]
	else:
		sysinfo["kcmd_isolcpus"] = None

	sysinfo["kcmd_maxcpus"] = None
	if kcmd.options.has_key("kcmd_maxcpus"):
		sysinfo["kcmd_maxcpus"] = kcmd.options["kcmd_maxcpus"]

	sysinfo["nic_kthread_affinities"] = get_nic_kthread_affinities(irqs)
	sysinfo["nic_kthread_rtprios"] = get_nic_kthread_rtprios(irqs, pfs)

	sysinfo["vsyscall64"] = None
	try:
		f = file("/proc/sys/kernel/vsyscall64")
		sysinfo["vsyscall64"] = int(f.readline())
		f.close()
	except:
		pass

	sysinfo["futex_performance_hack"] = None
	try:
		f = file("/proc/sys/kernel/futex_performance_hack")
		sysinfo["futex_performance_hack"] = int(f.readline())
		f.close()
	except:
		pass

	sysinfo["kcmd_idle"] = None
	if kcmd.options.has_key("kcmd_idle"):
		sysinfo["kcmd_idle"] = kcmd.options["kcmd_idle"]

	sysinfo["lock_stat"] = os.access("/proc/lock_stat", os.F_OK)

	app = pfs.find_by_name(app_process_name)
	if app:
		sysinfo["app_rtprio"] = pfs.get_rtprios(app_process_name)
		sysinfo["app_affinity"] = utilist.csv(utilist.hexbitmask(schedutils.get_affinity(app[0]),
												    int(sysinfo["nr_cpus"])), "%x")
		sysinfo["app_sched"] = schedutils.schedstr(schedutils.get_scheduler(app[0]))

		# Default: libc statically linked
		sysinfo["libc"] = None
		# Discover which libc is being used by the application
		smaps = procfs.smaps(app[0])
		if smaps:
			libc = smaps.find_by_name_fragment("/libc-")
			if libc:
				sysinfo["libc"] = libc[0].name
	else:
		sysinfo["app_rtprio"] = None
		sysinfo["app_affinity"] = None
		sysinfo["app_sched"] = None

	keys = sysinfo.keys()
	keys.sort()
	for key in keys:
		print "%s: %s" % ( key, sysinfo[key] )
