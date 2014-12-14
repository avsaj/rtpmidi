# -*- coding: utf8 -*-

from distutils.core import setup
from textwrap import dedent

setup(name='rtpmidi',
      version='0.7.1',
      description='Send and receive midi data over RTP',
      author=dedent('''
        Tristan Matthews
        Alexandre Quessy
        Simon Piette
        Philippe Chevry
        Koya Charles
        Antoine Collet
        Sylvain Cormier
        Étienne Désautels
        Hugo Boyer'''),
      author_email=dedent('''
        <tristan@sat.qc.ca>
        <alexandre@quessy.net>
        <simonp@sat.qc.ca>
        <pchevry@sat.qc.ca>
        <koya.charles@gmail.com>
        <antoine.collet@gmail.com>
        <studiozodiak@yahoo.ca>
        <etienne@teknozen.net>
        <ugomatik@gmail.com>'''),
      url='http://github.com/avsaj/rtpmidi',
      packages=['rtpmidi'])
