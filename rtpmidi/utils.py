#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Scenic
# Copyright (C) 2008 Société des arts technologiques (SAT)
# http://www.sat.qc.ca
# All rights reserved.
#
# This file is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# Scenic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Scenic. If not, see <http://www.gnu.org/licenses/>.
"""
Utilities only used within runner.py
"""
import re

def check_ip(address):
    """
    Check address format
    """
    if re.match('^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', address):
	    values = [int(i) for i in address.split('.')]
	    if ip_range(values):
		    return True
	    else:
		    return False
    else:
	    return False

def ip_range(nums):
    for num in nums:
        if num < 0 or num > 255:
            return False
    return True

def check_port(portnum):
    """
    Checks if the port is in a usable range.
    """
    #TODO: do not allow ports for which you must be root to use them.
    if 0 < portnum < 65535:
        return True
    else:
        return False
