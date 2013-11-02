#!/usr/bin/env python

# Copyright 2013 David Sanders

"""Simple script to estimate Linux memory fragmentation from /proc/buddyinfo

Based on a presentation from Samsung, which can be found at:
* https://github.com/dsanders11/scripts/blob/master/Linux_Memory_Fragmentation.pdf

"""

import platform
import sys

from optparse import OptionParser

def calculate_fragmentation():
    """ Calculates fragmentation from /proc/buddyinfo and populates a dict
    
    Returned dict is a nested dict describing the fragmentation. The first set
    of keys are by node (e.g. Node 0, Node 1), and the second is by zone (e.g.
    DMA, DMA32, Normal). Finally, the  last dict is keyed by memory order, and
    has a tuple value where the first value is the free page count, and the
    second is the calculated fragmentation as a percentage.
    
    """
    
    with open("/proc/buddyinfo", 'r') as buddyinfo_output:
        return _calculate_fragmentation(buddyinfo_output)

def print_fragmentation():
    """ Pretty prints fragmentation calculated from /proc/buddyinfo
    
    The output approximates that found in the Samsung presentation this script
    is based off of, leaving out any information (such as relocatable pages)
    which can not be derived from /proc/buddyinfo
    
    """

    frag_dict = calculate_fragmentation()
    
    _print_fragmentation(frag_dict, sys.stdout)

def _print_fragmentation(frag_dict, out):
    """ Internal version of print_fragmentation to make it unit testable """

    headers = ["Order", "Free Pages", "Fragmentation[%]"]
    widths = [4, 9, 15]
    
    write = out.write
    
    def columnize(columns, max_lens, widths, sep=4*' '):
        """ Helper to create a string with columns evenly spaced """
        
        padded_columns = []
        
        for _str, max_len, width in zip(columns, max_lens, widths):
            length_diff = max_len - len(str(_str))

            padded_column = ' ' * length_diff
            padded_column += str(_str)
            padded_column = padded_column.center(width)

            padded_columns.append(padded_column)
        
        return sep.join(padded_columns)

    for node, zone_dict in frag_dict.iteritems():
        for zone in zone_dict.iterkeys():
            total_free_pages = 0
            overall_frag_pct = 0
            
            write("{0}, Zone: {1}\n".format(node, zone))
            write(columnize(headers, map(len, headers), widths) + '\n')

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
                write(columnize(row, max_lens, widths, sep=5*' ') + '\n')

            # Calculate the mean over all orders
            overall_frag_pct /= 11
                
            write("Total Free Pages: {0}\n".format(total_free_pages))
            write("Overall Fragmentation: {0:.0%}\n".format(overall_frag_pct))
            write('\n')

def _calculate_fragmentation(buddyinfo_output):
    """ Internal version of calculate_fragmentation, to make it unit testable """

    frag_dict = {}
    
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
            
def __unit_test():
    """ Run some basic unit tests against the script """
    
    import unittest
    import StringIO
    import textwrap
    
    class TestCalculateFragmentation(unittest.TestCase):
        """ Test the _calculate_fragmentation function for some known values """
        
        def runTest(self):
            buddy_output = ["Node 0, zone      DMA      2      1      2      1"\
                            "   0      2      1      0      1      1      1 \n",
                            "Node 0, zone    DMA32  25386   2028     87     18"\
                            "   4      1      0      1      1      0      0 \n",
                            "Node 0, zone   Normal   1345     45     10      6"\
                            "   0      0      0      1      0      1      0 \n",
                            "Node 1, zone   Normal   5045     23     62      2"\
                            "   0      0      0      0      0      1      0 \n"]
                           
            frag_out = _calculate_fragmentation(buddy_output)

            self.assertEqual(frag_out.keys(), ["Node 0", "Node 1"])
            
            self.assertEqual(sorted(frag_out["Node 0"].keys()),
                             sorted(["DMA", "DMA32", "Normal"]))
                             
            for zone in frag_out["Node 0"].keys():
                self.assertEqual(sorted(frag_out["Node 0"][zone]), range(0, 11))
                
            dma_frag = [(2, 0.0000000000), (1, 0.0010309278), (2, 0.0020618556),
                        (1, 0.0061855670), (0, 0.0103092783), (2, 0.0103092783),
                        (1, 0.0432989690), (0, 0.0762886597), (1, 0.0762886597),
                        (1, 0.2082474226), (1, 0.4721649484)]
            
            dma_dict = frag_out["Node 0"]["DMA"]

            # Check within 9 places of fragmentation accuracy
            for order, expected in enumerate(dma_frag):
                free_pages, frag_pct = expected
                self.assertEqual(dma_dict[order][0], free_pages)
                self.assertAlmostEqual(dma_dict[order][1], frag_pct, 9)
                
            dma32_frag = [(25386, 0.0000000000), (2028, 0.8346813967),
                             (87, 0.9680410337),   (18, 0.9794831327),
                              (4, 0.9842177944),    (1, 0.9863220885),
                              (0, 0.9873742355),    (1, 0.9873742355),
                              (1, 0.9915828236),    (0, 1.0000000000),
                              (0, 1.0000000000)]
            
            dma32_dict = frag_out["Node 0"]["DMA32"]
            
            # Check within 9 places of fragmentation accuracy
            for order, expected in enumerate(dma32_frag):
                free_pages, frag_pct = expected
                self.assertEqual(dma32_dict[order][0], free_pages)
                self.assertAlmostEqual(dma32_dict[order][1], frag_pct, 9)
                
            normal_frag = [(1345, 0.0000000000), (45, 0.6218215441),
                             (10, 0.6634304207),  (6, 0.6819232547),
                              (0, 0.7041146555),  (0, 0.7041146555),
                              (0, 0.7041146555),  (1, 0.7041146555),
                              (0, 0.7632917244),  (1, 0.7632917244),
                              (0, 1.0000000000)]
            
            normal_dict = frag_out["Node 0"]["Normal"]
            
            # Check within 9 places of fragmentation accuracy
            for order, expected in enumerate(normal_frag):
                free_pages, frag_pct = expected
                self.assertEqual(normal_dict[order][0], free_pages)
                self.assertAlmostEqual(normal_dict[order][1], frag_pct, 9)
                             
            self.assertEqual(frag_out["Node 1"].keys(), ["Normal"])
            self.assertEqual(sorted(frag_out["Node 1"][zone]), range(0, 11))
            
            normal_frag = [(5045, 0.0000000000), (23, 0.8598943241),
                             (62, 0.8677347877),  (2, 0.9100051133),
                              (0, 0.9127322311),  (0, 0.9127322311),
                              (0, 0.9127322311),  (0, 0.9127322311),
                              (0, 0.9127322311),  (1, 0.9127322311),
                              (0, 1.0000000000)]
            
            normal_dict = frag_out["Node 1"]["Normal"]
            
            # Check within 9 places of fragmentation accuracy
            for order, expected in enumerate(normal_frag):
                free_pages, frag_pct = expected
                self.assertEqual(normal_dict[order][0], free_pages)
                self.assertAlmostEqual(normal_dict[order][1], frag_pct, 9)
            
    class TestPrintFragmentation(unittest.TestCase):
        """ Test the output of _print_fragmentation against a known good one """

        def runTest(self):
            frag_dict = {
                         "Node 0": {
                                    "DMA": {
                                            0: (2, 0.000), 1: (1, 0.001),
                                            2: (2, 0.002), 3: (1, 0.006),
                                            4: (0, 0.010), 5: (2, 0.010),
                                            6: (1, 0.043), 7: (0, 0.076),
                                            8: (1, 0.076), 9: (1, 0.208),
                                            10: (1, 0.472)
                                           },
                                    "Normal": {
                                               0: (1345, 0.000), 1: (45, 0.621),
                                               2:   (10, 0.663), 3:  (6, 0.681),
                                               4:    (0, 0.704), 5:  (0, 0.704),
                                               6:    (0, 0.704), 7:  (1, 0.704),
                                               8:    (0, 0.763), 9:  (1, 0.763),
                                               10:   (0, 1.000)
                                              }
                                   },
                         "Node 1": {
                                    "DMA32": {
                                              0: (25386, 0.000), 1: (2028, 0.834),
                                              2:    (87, 0.968), 3:   (18, 0.979),
                                              4:     (4, 0.984), 5:    (1, 0.986),
                                              6:     (0, 0.987), 7:    (1, 0.987),
                                              8:     (1, 0.991), 9:    (0, 1.000),
                                              10:    (0, 1.000)
                                             },
                                    "Normal": {
                                               0: (1345, 0.000), 1: (45, 0.621),
                                               2:   (10, 0.663), 3:  (6, 0.681),
                                               4:    (0, 0.704), 4:  (0, 0.704),
                                               6:    (0, 0.704), 5:  (1, 0.704),
                                               8:    (0, 0.763), 6:  (1, 0.763),
                                               10:   (0, 1.000)
                                              }
                                   }
                        }

            output = StringIO.StringIO()
            expected_output = """\
                              Node 0, Zone: DMA
                              Order    Free Pages    Fragmentation[%]
                                0          2                0%      
                                1          1                0%      
                                2          2                0%      
                                3          1                1%      
                                4          0                1%      
                                5          2                1%      
                                6          1                4%      
                                7          0                8%      
                                8          1                8%      
                                9          1               21%      
                               10          1               47%      
                              Total Free Pages: 1940
                              Overall Fragmentation: 8%
                              
                              Node 0, Zone: Normal
                              Order    Free Pages    Fragmentation[%]
                                0         1345               0%     
                                1           45              62%     
                                2           10              66%     
                                3            6              68%     
                                4            0              70%     
                                5            0              70%     
                                6            0              70%     
                                7            1              70%     
                                8            0              76%     
                                9            1              76%     
                               10            0             100%     
                              Total Free Pages: 2163
                              Overall Fragmentation: 66%
                              
                              Node 1, Zone: DMA32
                              Order    Free Pages    Fragmentation[%]
                                0        25386               0%     
                                1         2028              83%     
                                2           87              97%     
                                3           18              98%     
                                4            4              98%     
                                5            1              99%     
                                6            0              99%     
                                7            1              99%     
                                8            1              99%     
                                9            0             100%     
                               10            0             100%     
                              Total Free Pages: 30414
                              Overall Fragmentation: 88%
                              
                              Node 1, Zone: Normal
                              Order    Free Pages    Fragmentation[%]
                                0         1345               0%     
                                1           45              62%     
                                2           10              66%     
                                3            6              68%     
                                4            0              70%     
                                5            1              70%     
                                6            1              76%     
                                8            0              76%     
                               10            0             100%     
                              Total Free Pages: 1619
                              Overall Fragmentation: 54%
                              
                              """
            
            _print_fragmentation(frag_dict, output)
            
            frag_output = output.getvalue()

            # Whitespace insensitive, just checks the output content
            self.assertEqual(''.join(frag_output.split()),
                             ''.join(expected_output.split()))
            
            self.assertEqual(frag_output,
                             textwrap.dedent(expected_output),
                             "Whitespace sensitive test failed, check whitespace")
    
    suite = unittest.TestSuite()
    suite.addTest(TestCalculateFragmentation())
    suite.addTest(TestPrintFragmentation())
    
    runner = unittest.TextTestRunner()
    runner.run(suite)

if __name__ == '__main__':
    parser = OptionParser(usage="Usage: %prog [options]", version="%prog 0.1")
    parser.add_option("--test",
                      action="store_true", dest="unit_test", default=False,
                      help="run the unit test")

    (options, args) = parser.parse_args()
    
    if len(args) > 0:
        parser.parse_args(["--help"])

    if platform.system() != "Linux":
        print "ERROR: This script only works for Linux"
        exit(1)

    if options.unit_test:
        __unit_test()
    else:
        try:
            print_fragmentation()
        except IOError:
            print "ERROR: /proc/buddyinfo not readable. Does your kernel support it?"
            exit(1)