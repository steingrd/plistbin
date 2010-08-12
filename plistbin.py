#!/usr/bin/env python
# encoding: utf-8

import struct, plistlib, datetime

# TODO
# - dicts with more than 14 keys
# - allow pathOrFile to be a file-like object
# - raise TypeError for unsupported types
# - add writePlistToString to match plistlib API
# - implement binary plist parser (readPlist)
# - support >8 byte integers

# TODO implement support for these data types:
# - uid

__all__ = ['writePlist', 'Data']

def writePlist(rootObject, pathOrFile):
    writer = BinaryPropertyListWriter(rootObject, pathOrFile)
    writer.write()
    
class Data(object):
    """ Wrapper for binary data. """
    def __init__(self, data):
        self.data = data

class PlistObject(object): 
    def __init__(self, plist_type, value, inline=False):
        self.value = value
        self.inline = inline
        self.plist_type = plist_type
        
    def __repr__(self):
        return self.plist_type
        
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
        objects_table.append(PlistObject('Boolean', unknown_object))
    elif isinstance(unknown_object, int):
        objects_table.append(PlistObject('Integer', unknown_object))    
    elif isinstance(unknown_object, float):
        objects_table.append(PlistObject('Real', unknown_object))    
    elif isinstance(unknown_object, str):
        objects_table.append(PlistObject('AsciiString', unknown_object))
    elif isinstance(unknown_object, unicode):
        objects_table.append(PlistObject('UnicodeString', unknown_object))
    elif isinstance(unknown_object, datetime.datetime):
        objects_table.append(PlistObject('Date', unknown_object))
    elif isinstance(unknown_object, dict):
        objects_table.append(PlistObject('Dict', unknown_object))
        # TODO support more than 14 keys
        for key, val in unknown_object.iteritems():
            objects_table.append(PlistObject('KeyRef', key))
            objects_table.append(PlistObject('ObjRef', val))
        for key, val in unknown_object.iteritems():
            flatten_to_table(key, objects_table)
            flatten_to_table(val, objects_table)
    elif isinstance(unknown_object, (list, tuple)):
        objects_table.append(PlistObject('Array', unknown_object))
        if len(unknown_object) > 14:
            objects_table.append(PlistObject('Integer', len(unknown_object), inline=True))
        for obj in unknown_object:
            objects_table.append(PlistObject('ObjRef', obj))
        for obj in unknown_object:
            flatten_to_table(obj, objects_table)
    # Data instances from plistlib is also supported
    elif isinstance(unknown_object, (Data, plistlib.Data)):
        objects_table.append(PlistObject('Data', unknown_object.data))

def flatten(unknown_object):
    objects_table = []
    flatten_to_table(unknown_object, objects_table)
    return objects_table

class BinaryPropertyListWriter(object):
    def __init__(self, root_object, path_or_file):
        self.out = file(path_or_file, 'wb')
        self.object_table = flatten(root_object)
        
        # calculate the size of objref ints by counting objrefs and keyrefs
        num_objrefs = sum( 1 for obj in self.object_table if obj.plist_type.endswith('Ref') )
        self.objref_size = bytes_for_number(num_objrefs)
        
        self.offset_table = []
        self.current_offset = 0
        self.object_count = 0
        self.offset_count = 0

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
        
    def write_dict(self, dict_object):
        # TODO check length and write correct marker
        marker_byte = 0xd0 | len(dict_object.value)
        
        self.out.write(self.single_byte.pack(marker_byte))
        self.object_count += 1
        self.offset_count = self.object_count
        self.offset_table.append(self.current_offset)
        self.current_offset += 1
        
    def write_keyref(self, keyref_object):
        s = self.struct_for_byte_size[self.objref_size]
        self.out.write(s.pack(self.offset_count))
        self.offset_count += 1
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
            self.write_integer(PlistObject('Integer', data_size, inline=True))
            
        self.current_offset += 1 + data_size # 1 for the marker byte
        self.out.write(data)
        
    def write_unicode_string(self, unicode_string_object):
        data = unicode_string_object.value.encode('utf_16_be')
        length = len(unicode_string_object.value)
        
        self.offset_table.append(self.current_offset)
        self.object_count += 1
        
        if length < 15:
            marker_byte = 0x60 | length
            self.out.write(self.single_byte.pack(marker_byte))
        else:
            marker_byte = 0x6f
            self.out.write(self.single_byte.pack(marker_byte))
            # size is written as an integer following the marker byte
            self.write_integer(PlistObject('Integer', length, inline=True))
            
        self.current_offset += 1 + len(data) # 1 byte marker
        self.out.write(data)
        
    def write_data(self, data_object):
        length = len(data_object.value)
        if length < 15:
            marker_byte = 0x40 | length
            self.out.write(self.single_byte.pack(marker_byte))
        else:
            marker_byte = 0x4f
            self.out.write(self.single_byte.pack(marker_byte))
            self.write_integer(PlistObject('Integer', length, inline=True))
        self.object_count += 1
        self.current_offset += 1 + length
        self.out.write(data_object.value)
        # TODO figure out why this backspace byte is there. here's the story:
        # so, it turns out that the plutil utility puts a 0x08 byte at the
        # end of all byte streams (backspace). it seems strange, but here 
        # it is. even stranger is the fact that the offset to the offset
        # table is not incremented. that would mean that the offset table
        # has the wrong offset, no?
        self.out.write('\x08')
        
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
        
    def write_real(self, real_object):
        self.out.write('\x23')
        self.out.write(struct.pack('>d', real_object.value))
        self.offset_table.append(self.current_offset)
        self.current_offset += 9
        self.object_count += 1
        
    def write_datetime(self, datetime_object):
        self.out.write('\x33')
        # compute the value of the double that stores the time. Cocoa uses
        # 2001-01-01T00:00:00 as epoch, negative numbers means before epoch.
        epoch = datetime.datetime(2001, 1, 1, 0, 0, 0, 0)
        delta = datetime_object.value - epoch
        seconds = (delta.days * 86400) + delta.seconds

        self.out.write(struct.pack('>d', seconds))
        self.offset_table.append(self.current_offset)
        self.current_offset += 9
        self.object_count += 1
        
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
        methods = {
            'Array': self.write_array,
            'ObjRef': self.write_objref,
            'Integer': self.write_integer,
            'Boolean': self.write_boolean,
            'AsciiString': self.write_ascii_string,
            'UnicodeString': self.write_unicode_string,
            'Dict': self.write_dict,
            'KeyRef': self.write_keyref,
            'Data': self.write_data,
            'Real': self.write_real,
            'Date': self.write_datetime
        }
        
        for obj in self.object_table:
            m = methods[obj.plist_type]
            m(obj)
        
    def write_offsets(self):
        s = self.struct_for_byte_size[bytes_for_number(self.current_offset)]
        for offset in self.offset_table:
            self.out.write(s.pack(offset))
    
    def write_trailer(self):
        trailer = struct.Struct('>6xBBQQQ')
        offset_int_size = bytes_for_number(self.current_offset)
        values = (
            # trailer starts with 6 unused bytes
            offset_int_size,     # 1 byte offset int size
            self.objref_size,    # 1 byte objref int size
            self.object_count,   # 8 byte object count
            0,                   # 8 byte top object offset (always 0 in this implementation)
            self.current_offset, # 8 byte offset table offset
        )
        self.out.write(trailer.pack(*values))

    def write(self):
        self.write_headers()
        self.write_objects()
        self.write_offsets()
        self.write_trailer()
        self.out.close() # TODO do not close if file object was given
                
