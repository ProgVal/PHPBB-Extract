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

import os
import logging
import argparse
import html2rest
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

def extract_category(url, destination):
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
                    os.path.join(destination, folder))
        else:
            titles = category('ul.topiclist.forums li dl dt a.forumtitle')
            for title in map(pq, titles):
                folder = title('a').attr('href').rsplit('/', 2)[1]
                index.write('    %s/index.rst\n' % folder)
                extract_forum(title.attr('href'),
                        os.path.join(destination, folder))

def extract_forum(url, destination):
    logging.info('Mirroring to %s (forum).' % destination)
    extract_category(url, destination)

    index = os.path.join(destination, 'index.rst')
    # Do not remove it; have been created by extract_category.
    index = open(index, 'a')
    index.write('\n\n.. toctree::\n    :maxdepth: 1\n\n')
    
    topics = load(url)('div.forumbg div.inner ul.topics li dl')
    for topic in map(pq, topics):
        link = pq(topic('dt a')).attr('href')
        slug = link.rsplit('/', 1)[1][:-len('.html')]
        index.write('    %s.rst\n' % slug)
        extract_topic(link, os.path.join(destination, slug + '.rst'))

def extract_topic(url, destination):
    logging.info('Mirroring to %s (topic).' % destination)

    messages = []
    def add_messages(page):
        messages.extend(page('div#page-body div.post div.inner div.postbody'))
    page = load(url)
    add_messages(page)
    while page('form.viewtopic'):
        page = load('form.viewtopic fieldset a.right-box').attr('href')
        add_messages(page)

    if os.path.isfile(destination):
        os.unlink(destination)
    topic = open(destination, 'a')
    link = pq(page('div#page-body h2 a'))
    title = link.text().encode('utf8')
    slug = link.attr('href').rsplit('/', 1)[1]
    topic.write('.. _topic_%s:\n\n%s\n%s\n\n' % (slug, title, '*'*len(title)))

    for message in map(pq, messages):
        id_ = message('h3 a').attr('href').rsplit('#p', 1)[1]
        title = message('h3 a').text().encode('utf8')
        author = message('p.author strong span').text()
        content = message('div.content').html().encode('utf8')

        topic.write('.. _post_%s_%s:\n\n' % (slug, id_))
        topic.write('%s (%s)\n%s\n\n' %
                (title, author, '='*(len(title) + 3 + len(author))))
        write_message(content, topic, url, destination)
        topic.write('\n\n')
    topic.close()

class Parser(html2rest.Parser):
    def start_br(self, data):
        self.write('\n\n')
    def close(self):
        self.write('\n\n')
        for href, link in self.hrefs.items():
            if href[0] != '#' and not link.startswith('http'):
                self.writeline('.. _%s: %s' % (link, href))



def write_message(content, fd, url, destination):
    parser = Parser(fd, 'utf8', destination, url)
    parser.feed(content.decode('utf8'))
    parser.close()


def main():
    parser = argparse.ArgumentParser(description='Extract messages '
            'from a PHPBB forum.')
    parser.add_argument('base_url')
    parser.add_argument('--dest', default='mirror/')
    args = parser.parse_args()

    base_url = args.base_url
    destination = args.dest

    extract_category(base_url, destination)

if __name__ == '__main__':
    main()
