#!/usr/bin/env python
# -*- coding: utf-8 -*-

from distutils.core import setup


long_description = """
==========================================================
plistbin - generate and parse binary plist files in Python
==========================================================

The plistbin Python package provides an interface for generating and parsing
binary "property list" files as used on the Mac OS X platform.

""" + "\n\n" + open('CHANGELOG.txt').read()

setup(name='plistbin',
      version='0.1',
      author='Steingrim Dovland',
      author_email='steingrd@ifi.uio.no',
      url='http://wiki.github.com/steingrd/plist-binary',
      description='Generate and parse binary property list files',
      long_description=long_description,
      py_modules=['plistbin']
      classifiers=['Development Status :: 4 - Beta',
                   'Intended Audience :: Developers',
                   'License :: OSI Approved :: BSD License',
                   'Operating System :: OS Independent',
                   'Programming Language :: Python'])
