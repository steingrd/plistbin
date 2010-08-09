#!/usr/bin/env python
# encoding: utf-8

from dircache import listdir
from os.path import join, dirname
import plistlib, filecmp

from nose.tools import *

import plistbin

def test_flatten_integer():
    f = plistbin.flatten(42)
    assert_equals('[Integer]', repr(f))
    assert_equals(42, f[0].value)

def test_flatten_boolean():
    f = plistbin.flatten(True)
    assert_equals('[Boolean]', repr(f))
    assert_equals(True, f[0].value)

def test_bytecode_string():
    f = plistbin.flatten('True')
    assert_equals('[AsciiString]', repr(f))
    assert_equals('True', f[0].value)

def test_flatten_lists_and_tuples_to_array():
    # simple list of primitives
    f = plistbin.flatten([10, 11, 12])
    assert_equals('[Array, ObjRef, ObjRef, ObjRef, Integer, Integer, Integer]', repr(f))
    # list with non-primitive values
    f = plistbin.flatten([(1,), (4,)])
    assert_equals('[Array, ObjRef, ObjRef, Array, ObjRef, Integer, Array, ObjRef, Integer]', repr(f))

def test_generate_plist_files_and_match_pregenerated():
    files = find_xml_files_and_binary_files()
    for t in files:
        generate_and_compare(t[0], t[1])

def generate_and_compare(xml_filename, binary_filename):
    """
    Reads the data in xml_filename using stdlib module plistlib and generates
    a binary plist file from the resulting data. This file is compared to a 
    pre-generated file named binary_filename and an assertion is raised if the
    files are not equal.
    """
    # read the xml file using the stdlib module plistlib
    data = plistlib.readPlist(xml_filename)
    
    # write the data from the xml file to a binary file
    generate_binary_filename = binary_filename + "_generated"
    plistbin.writePlist(data, generate_binary_filename)
    
    # compare the files using the stdlib filecmp module, last param
    # instructs filecmp to do a non-shallow compare
    message = "file is not matching pre-generated plist: " + generate_binary_filename
    assert_true(filecmp.cmp(binary_filename, generate_binary_filename, False), msg=message)

def find_xml_files_and_binary_files(): 
    """
    Returns a list of tuples of full pathnames for the files in the files/ 
    subdirectory. Each tuple contains (xml filename, binary filename) where 
    xml filename is the xml property list and binary filename is the name of 
    the corresponding binary plist file.
    
    """
    files_directory = join(dirname(__file__), 'files')
    files = listdir(files_directory)
    result = []
    for filename in files:
        if filename.startswith('xml'):
            binary_filename = filename.replace('xml', 'bin')
            result += [(join(files_directory, filename), join(files_directory, binary_filename))]
    return result

