#!/usr/bin/env python

import struct, sys

data = open(sys.argv[1]).read()

trailer_struct = struct.Struct('>6BBBQQQ')
trailer_data = data[-32:]
trailer = trailer_struct.unpack(trailer_data)

print 'offset int size', trailer[6]
print 'objref int size', trailer[7]
print 'object count', trailer[8]
print 'top object offset', trailer[9]
print 'offset table offset', trailer[10]