#!/usr/bin/env python

# Copyright 2013 David Sanders

"""Simple script to estimate Linux memory fragmentation from /proc/buddyinfo

Based on a presentation from Samsung, which can be found at:
* http://elinux.org/images/a/a8/Controlling_Linux_Memory_Fragmentation_and_Higher_Order_Allocation_Failure-_Analysis,_Observations_and_Results.pdf

"""

import platform

from optparse import OptionParser

def calculate_fragmentation():
    """ Calculates fragmentation from /proc/buddyinfo and populates a dict
    
    Returned dict is a nested dict describing the fragmentation. The first set
    of keys are by node (e.g. Node 0, Node 1), and the second is by zone (e.g.
    DMA, DMA32, Normal). Finally, the  last dict is keyed by memory order, and
    has a tuple value where the first value is the free page count, and the
    second is the calculated fragmentation as a percentage.
    
    """

    frag_dict = {}
    
    with open("/proc/buddyinfo", 'r') as buddyinfo_output:
        for line in buddyinfo_output:
            node, frag_info = line.split(',')
            zone, free_pages = frag_info.split()[1], frag_info.split()[2:]

            # Convert all the strings to ints
            free_pages = map(int, free_pages)

            frag_dict.setdefault(node, {})
            frag_dict[node][zone] = {}

            total_free_pages = 0

            for order, free_count in enumerate(free_pages):
                total_free_pages += (2**order) * free_count

            for order, free_count in enumerate(free_pages):
                frag_pct = 0

                # really inefficient, but who cares
                for _order, _free_count in enumerate(free_pages[order:]):
                    frag_pct += (2**(_order + order)) * _free_count
                    
                frag_pct = float(total_free_pages - frag_pct)/total_free_pages
                
                frag_dict[node][zone][order] = (free_count, frag_pct)

    return frag_dict

def print_fragmentation():
    """ Pretty prints fragmentation calculated from /proc/buddyinfo
    
    The output approximates that found in the Samsung presentation this script
    is based off of, leaving out any information (such as relocatable pages)
    which can not be derived from /proc/buddyinfo
    
    """

    frag_dict = calculate_fragmentation()
    
    headers = ["Order", "Free Pages", "Fragmentation[%]"]
    widths = [4, 9, 15]
    
    def columnize(columns, max_lens, widths, sep=4*' '):
        """ Helper to create a string with columsn evenly spaced """
        
        padded_columns = []
        
        for _str, max_len, width in zip(columns, max_lens, widths):
            length_diff = max_len - len(str(_str))

            padded_column = ' ' * length_diff
            padded_column += str(_str)
            padded_column = padded_column.center(width)

            padded_columns.append(padded_column)
        
        return sep.join(padded_columns)
    
    centerize = lambda _str, width: str(_str).center(width)

    for node, zone_dict in frag_dict.iteritems():
        for zone in zone_dict.iterkeys():
            total_free_pages = 0
            overall_frag_pct = 0
            
            print "{0}, Zone: {1}".format(node, zone)
            print columnize(headers, map(len, headers), widths)

            rows = []
            max_lens = [0, 0, 0]
            
            for order, frag_info in zone_dict[zone].iteritems():
                free_count, frag_pct = frag_info

                total_free_pages += (2**order) * free_count
                overall_frag_pct += frag_pct

                frag_pct = "{0:.0%}".format(frag_pct)

                rows.append((order, free_count, frag_pct))

            # Find max length for each column for use in pretty printing
            for order, free_count, frag_pct in rows:
                max_lens[0] = max(len(str(order)), max_lens[0])
                max_lens[1] = max(len(str(free_count)), max_lens[1])
                max_lens[2] = max(len(str(frag_pct)), max_lens[2])

            for row in rows:
                print columnize(row, max_lens, widths, sep=5*' ')

            # Calculate the mean over all orders
            overall_frag_pct /= 11
                
            print "Total Free Pages: {0}".format(total_free_pages)
            print "Overall Fragmentation: {0:.0%}".format(overall_frag_pct)
            print

if __name__ == '__main__':
    parser = OptionParser(usage="Usage: %prog", version="%prog 0.1")

    (options, args) = parser.parse_args()

    if platform.system() != "Linux":
        print "ERROR: This script only works for Linux"
        exit(1)

    try:
        print_fragmentation()
    except IOError:
        print "ERROR: /proc/buddyinfo not readable. Does your kernel support it?"
        exit(1)