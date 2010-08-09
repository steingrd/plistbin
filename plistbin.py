#!/usr/bin/env python
# encoding: utf-8

import struct

# TODO implement support for these data types:
# - unicode strings
# - base64 encoded data
# - real
# - date
# - null
# - uid
# - dict
# - set

def writePlist(rootObject, pathOrFile):
    writer = BinaryPropertyListWriter(rootObject, pathOrFile)
    writer.write()

class PlistObject(object): 
    def __init__(self, value, inline=False):
        self.value = value
        self.inline = inline

class Boolean(PlistObject):
    def __repr__(self):
        return 'Boolean'

class Integer(PlistObject):    
    def __repr__(self):
        return 'Integer'
    
class Array(PlistObject):
    def __repr__(self):
        return 'Array'
    
class ObjRef(PlistObject):
    def __repr__(self):
        return 'ObjRef'

class AsciiString(PlistObject):
    def __repr__(self):
        return 'AsciiString'
        
def bytes_for_number(number):
    """
    Returns the number of bytes required to store `number`. Returns a power
    of 2 except for numbers requiring more than 8 bytes when it returns the
    number of bytes required.
    
    """
    mask = ~0
    size = 0
    while (number & mask) != 0:
        size += 1
        mask = mask << 8
    
    # ensure size is a power of 2 if below 8    
    while (size != 1 and size != 2 and size != 4 and size != 8) and size <= 8:
        size += 1
        
    return size

def flatten_to_table(unknown_object, objects_table):
    if isinstance(unknown_object, bool):
        objects_table.append(Boolean(unknown_object))
    elif isinstance(unknown_object, int):
        objects_table.append(Integer(unknown_object))    
    elif isinstance(unknown_object, str):
        objects_table.append(AsciiString(unknown_object))
    elif isinstance(unknown_object, (list, tuple)):
        objects_table.append(Array(unknown_object))
        if len(unknown_object) > 14:
            objects_table.append(Integer(len(unknown_object), inline=True))
        for obj in unknown_object:
            objects_table.append(ObjRef(obj))
        for obj in unknown_object:
            flatten_to_table(obj, objects_table)

def flatten(unknown_object):
    objects_table = []
    flatten_to_table(unknown_object, objects_table)
    return objects_table

class BinaryPropertyListWriter(object):
    def __init__(self, root_object, path_or_file):
        self.out = file(path_or_file, 'wb')
        self.object_table = flatten(root_object)
        
        # calculate the size of objref ints by counting objrefs
        num_objrefs = sum( 1 for obj in self.object_table if isinstance(obj, ObjRef) )
        self.objref_size = bytes_for_number(num_objrefs)
        
        self.offset_table = []
        self.current_offset = 0
        self.object_count = 0
        self.offset_count = 0
        
        self.methods = {
            Array: self.write_array,
            ObjRef: self.write_objref,
            Integer: self.write_integer,
            Boolean: self.write_boolean,
            AsciiString: self.write_ascii_string,
        }
        self.initialize_structs()
        
    def initialize_structs(self):
        self.struct_for_byte_size = {
            1: struct.Struct('>B'),
            2: struct.Struct('>H'),
            4: struct.Struct('>L'),
            8: struct.Struct('>Q')
        }
        self.single_byte = self.struct_for_byte_size[1]
        
    def write_array(self, array_object):
        marker_byte = 0xaf
        if len(array_object.value) < 15:
            marker_byte = 0xa0 | len(array_object.value)
            
        self.out.write(self.single_byte.pack(marker_byte))
        self.object_count += 1
        # the offset_count is used as a temporary counter for the objref
        # values. as each objref is written, the counter is incremented.
        self.offset_count = self.object_count
        self.offset_table.append(self.current_offset)
        self.current_offset += 1
        
    def write_objref(self, objref_object):
        s = self.struct_for_byte_size[self.objref_size]
        self.out.write(s.pack(self.offset_count))
        self.offset_count += 1
        self.current_offset += self.objref_size
        
    def write_ascii_string(self, ascii_string_object):
        data = ascii_string_object.value
        data_size = len(data)
        
        self.offset_table.append(self.current_offset)
        self.object_count += 1
        
        if data_size < 15:
            marker_byte = 0x50 | data_size
            self.out.write(self.single_byte.pack(marker_byte))
        else:
            marker_byte = 0x5f
            self.out.write(self.single_byte.pack(marker_byte))
            # size is written as an integer following the marker byte
            self.write_integer(Integer(data_size, inline=True))
        self.current_offset += 1 + data_size # 1 for the marker byte
        self.out.write(data)
        
    def write_integer(self, integer_object):
        bytes_required = bytes_for_number(integer_object.value)
        if not integer_object.inline:
            self.offset_table.append(self.current_offset)
            self.object_count += 1
        self.current_offset += 1 + bytes_required
        self.write_integer_bytes(integer_object.value, bytes_required)
        
    def write_integer_bytes(self, integer, bytes_required):
        if bytes_required == 1:
            self.out.write('\x10')
        elif bytes_required == 2: 
            self.out.write('\x11')
        s = self.struct_for_byte_size[bytes_required]
        self.out.write(s.pack(integer))
        
    def write_boolean(self, boolean_object):
        if boolean_object.value:
            byte = '\x09'
        else:
            byte = '\x08'
        self.out.write(byte)
        self.offset_table.append(self.current_offset)
        self.current_offset += 1
        self.object_count += 1

    def write_headers(self):
        self.out.write('bplist00')
        self.current_offset += 8
        
    def write_objects(self):
        for obj in self.object_table:
            m = self.methods[type(obj)]
            m(obj)
        
    def write_offsets(self):
        s = self.struct_for_byte_size[bytes_for_number(self.current_offset)]
        for offset in self.offset_table:
            self.out.write(s.pack(offset))
    
    def write_trailer(self):
        trailer = struct.Struct('>6BBBQQQ')
        offset_int_size = bytes_for_number(self.current_offset)
        values = (
            0, 0, 0, 0, 0, 0,        # 6 unused bytes
            offset_int_size,         # 1 byte offset int size
            self.objref_size,        # 1 byte objref int size
            self.object_count,       # 8 byte object count
            0,                       # 8 byte top object offset (always 0 in this implementation)
            self.current_offset,     # 8 byte offset table offset
        )
        self.out.write(trailer.pack(*values))

    def write(self):
        self.write_headers()
        self.write_objects()
        self.write_offsets()
        self.write_trailer()
        self.out.close() # TODO do not close if file object was given
                