#!/usr/bin/env python

###
# Copyright (c) 2012, Valentin Lorentz
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

import re
import os
import urllib2
import logging
import argparse
import html2rest
import multiprocessing
from pyquery import PyQuery as pq

logging.basicConfig(level=logging.INFO)

cache = {}

def load(url):
    if url in cache:
        return cache[url]
    else:
        try:
            page = pq(url)
        except KeyboardInterrupt:
            exit()
        cache[url] = page
        return page

def extract_category(url, destination, base_url):
    logging.info('Mirroring to %s (category).' % destination)
    assert '..' not in destination
    if not os.path.isdir(destination):
        assert not os.path.isfile(destination)
        os.mkdir(destination)

    index = os.path.join(destination, 'index.rst')
    if os.path.isfile(index):
        os.unlink(index)
    index = open(index, 'a')
    page = load(url)
    link = page('div#page-body h2 a')
    if link:
        slug = link.attr('href').rsplit('/', 2)[1]
        title = link.text().encode('utf8')
        index.write('.. _cat_%s:\n\n%s\n%s\n\n' % (slug, title, '^'*len(title)))
    index.write('.. toctree::\n    :maxdepth: 2\n\n')

    categories = page('div#page-body div.forabg div.inner')
    for category in map(pq, categories):
        title = pq(category('li.header dl dt a'))
        if title:
            assert len(title) == 1, title
            title = pq(title[0])
            slug = title.attr('href')
            folder = slug.rsplit('/', 2)[1]
            index.write('    %s/index.rst\n' % folder)
            extract_category(slug,
                    os.path.join(destination, folder),
                    base_url)
        else:
            titles = category('ul.topiclist.forums li dl dt a.forumtitle')
            for title in map(pq, titles):
                folder = title('a').attr('href').rsplit('/', 2)[1]
                index.write('    %s/index.rst\n' % folder)
                extract_forum(title.attr('href'),
                        os.path.join(destination, folder),
                        base_url)

def extract_forum(url, destination, base_url):
    logging.info('Mirroring to %s (forum).' % destination)
    extract_category(url, destination, base_url)

    index = os.path.join(destination, 'index.rst')
    # Do not remove it; have been created by extract_category.
    index = open(index, 'a')
    index.write('\n\n.. toctree::\n    :maxdepth: 1\n\n')
    
    topics = []
    def add_topics(page):
        topics.extend(page('div.forumbg div.inner ul.topics li dl'))
    page = load(url)
    add_topics(page)
    while page('form fieldset.display-options'):
        page = load(page('form fieldset.display-options a.right-box').attr('href'))
        add_topics(page)
    topics_in_index = multiprocessing.Queue()
    processes = []
    for topic in map(pq, topics):
        link = pq(topic('dt a')).attr('href')
        slug = link.rsplit('/', 1)[1][:-len('.html')]

        def _extract_topic_wrapper():
            try:
                if extract_topic(link, os.path.join(destination, slug + '.rst'), base_url):
                    topics_in_index.put(slug)
            finally:
                running_processes.release()
        running_processes.acquire()
        process = multiprocessing.Process(target=_extract_topic_wrapper)
        process.start()
        processes.append(process)
    for process in processes:
        process.join()
    while not topics_in_index.empty():
        index.write('    %s.rst\n' % topics_in_index.get())
    index.close()

def extract_topic(url, destination, base_url):
    logging.info('Mirroring to %s (topic).' % destination)

    messages = []
    def add_messages(page):
        messages.extend(page('div#page-body div.post div.inner div.postbody'))

    try:
        page = load(url)
    except urllib2.HTTPError:
        return False


    if os.path.isfile(destination):
        os.unlink(destination)
    topic = open(destination, 'a')
    topic.write(
        '.. role:: underline\n'
        '   :class: underline\n\n')
    link = pq(page('div#page-body h2 a'))
    title = link.text().encode('utf8')
    slug = link.attr('href').rsplit('/', 1)[1]
    topic.write('.. _topic_%s:\n\n%s\n%s\n\n' % (slug, title, '*'*len(title)))

    add_messages(page)
    while page('form#viewtopic'):
        page = load(page('form#viewtopic fieldset a.right-box').attr('href'))
        add_messages(page)

    for message in map(pq, messages):
        id_ = message('h3 a').attr('href').rsplit('#p', 1)[1]
        title = message('h3 a').text().encode('utf8')
        author = message('p.author strong').text().encode('utf8')
        content = message('div.content').html().encode('utf8')

        topic.write('.. _post_%s_%s:\n\n' % (slug, id_))
        topic.write('%s (%s)\n%s\n\n' %
                (title, author, '='*(len(title) + 3 + len(author))))
        write_message(content, topic, url, destination, base_url)
        topic.write('\n\n')
    topic.close()

    return True

class Infinite(int):
    def __gt__(self, other):
        return True
    def __ge__(self, other):
        return True
    def __lt__(self, other):
        return False
    def __le__(self, other):
        return False
    def __sub__(self, other):
        return Infinite()

class LineBuffer(html2rest.LineBuffer):
    """LineBuffer without wrapping."""
    def __init__(self):
        self._lines = []
        self._wrapper = html2rest.TextWrapper(width=Infinite())

class Parser(html2rest.Parser):
    def __init__(self, *args, **kwargs):
        html2rest.Parser.__init__(self, *args, **kwargs)
        self.linebuffer = LineBuffer()
    def start_br(self, data):
        self.write('\n\n')
    def start_u(self, data):
        self.data(':underline:`')
    def end_u(self):
        self.data('` ')
    def end_b(self):
        self.data('** ')
    def close(self):
        self.write('\n\n')
        for href, link in self.hrefs.items():
            if href[0] != '#' and not link.startswith('http'):
                self.writeline('.. _%s: %s' % (link, href))
    def start_li(self, attrs):
        if self.lists:
            html2rest.Parser.start_li(self, attrs)
    def end_li(self):
        if self.lists:
            html2rest.Parser.end_li(self)
    def start_phpbbextractlink(self, attrs):
        self.data('<%s>' % attrs[0][1])
    def unknown_starttag(self, tag, attrs):
        if tag.startswith('topic_'): # This is a reference:
            assert attrs == [], attrs
            self.data('<%s>' % tag)
        else:
            html2rest.Parser.unknown_starttag(self, tag, attrs)


def style_replace(data):
    _style_regexp = re.compile('<span style="(?P<style>[^"]+)"> *(?P<content>[^<]*?) *</span>')
    def _style_replace(match):
        style = match.group('style')
        content = match.group('content')
        if style == 'font-weight: bold':
            return '<b>%s</b>' % content
        if style == 'text-decoration: underline':
            return '<u>%s</u>' % content
        else:
            return content
    return _style_regexp.sub(_style_replace, data)

def link_replace(data, base_url):
    _link_regexp = re.compile('<a( class="postlink")? href="(?P<link>[^"]+)"( class="postlink")?>(?P<content>.*?)</a>')
    def _link_replace(match):
        content = match.group('content')
        link = match.group('link')
        return '`%s <phpbbextractlink href="%s">`_' % (content, link)

    _internal_link_regexp = re.compile('<a( class="postlink")? href="%s([^"]*)/(?P<slug>[^"]+).html(#p(?P<postid>[0-9]+))?"( class="postlink")?>(?P<content>.*?)</a>' % base_url)
    def _internal_link_replace(match):
        content = match.group('content')
        slug = match.group('slug')
        postid = match.group('postid')
        post = ('_' + postid) if postid else ''
        return ':ref:`%s <topic_%s%s>`' % (content, slug, post)
    return _link_regexp.sub(_link_replace, _internal_link_regexp.sub(_internal_link_replace, data))

def write_message(content, fd, url, destination, base_url):
    parser = Parser(fd, 'utf8', destination, url)
    content = style_replace(content.decode('utf8'))
    content = link_replace(content, base_url)
    parser.feed(content)
    parser.close()

running_processes = None

def main():
    global running_processes
    parser = argparse.ArgumentParser(description='Extract messages '
            'from a PHPBB forum.')
    parser.add_argument('base_url')
    parser.add_argument('--dest', default='mirror/')
    parser.add_argument('-j', type=int, default=4,
            help='Number of processes to spawn.')
    args = parser.parse_args()

    base_url = args.base_url
    destination = args.dest
    running_processes = multiprocessing.Semaphore(args.j)

    staticdir = os.path.join(destination, '_static')
    css = os.path.join(staticdir, 'phpbb_import.css')
    if not os.path.isdir(staticdir):
        os.mkdir(staticdir)
    if os.path.isfile(css):
        os.unlink(css)
    with open(css, 'a') as css:
        css.write('@import url("default.css");\n\n'
            'span.underline {\n'
            '   text-decoration: underline;\n'
            '}\n')
    extract_category(base_url, destination, base_url)

if __name__ == '__main__':
    main()
