#!/usr/bin/python

import sys
import os.path


NUM_CHAR = '#'
ANCHOR_PREFIX = '[anchor:'
ANCHOR_SUFFIX = ']'
REF_PREFIX = '[ref:'
REF_SUFFIX = ']'
LINE_BREAK = '-'

class ListItemBase(object):

    def __init__(self, values=None):
        self.value_set = values
        self.pos = -1

    def inc(self):
        self.pos = self.pos + 1
        if self.pos >= len(self.value_set):
            raise Exception('Too many items in this list: %d' % self.pos)

    def reset(self):
        self.pos = -1


    def get(self):
        return self.value_set[self.pos]

class ListItemNone(ListItemBase):
    def inc(self):
        pass

    def reset(self):
        pass

    def get(self):
        pass

class ListItemNum(ListItemBase):

    def __init__(self):
        ListItemBase.__init__(self)
        self.value = 0

    def inc(self):
        self.value = self.value + 1

    def reset(self):
        self.value = 0

    def get(self):
        return self.value

class ListItemABC(ListItemBase):

    def __init__(self):
        ListItemBase.__init__(self,
                            ['a', 'b', 'c', 'd',
                             'e', 'f', 'g', 'h',
                             'i', 'j', 'k', 'l',
                             'm', 'n', 'o', 'p'])



class ListItemIII(ListItemBase):

    def __init__(self):
        ListItemBase.__init__(self,
                              ['i', 'ii', 'iii',
                               'iv', 'v', 'vi', 'vii',
                               'viii', 'ix', 'x'])


class WikiRef(object):

    def __init__(self, filename):
        self.level = 0
        self.filename = filename
        self.cur_id = [
            ListItemNone(),
            ListItemNum(),
            ListItemABC(),
            ListItemIII(),
            ListItemNum(),
            ListItemABC(),
            ListItemIII()
        ]

    def check_level(self, line):
        if not line.strip():
            return None

        if not line.strip(LINE_BREAK).strip():
            return 0

        i = 0
        while line[i] == NUM_CHAR:
            i = i + 1

        if i > 0:
            return i

        return None

    def check_anchor(self, line):
        level = self.level
        anchor_end = level + len(ANCHOR_PREFIX)
        if line[level:anchor_end] == ANCHOR_PREFIX:
            i = anchor_end
            while line[i] != ANCHOR_SUFFIX:
                i = i + 1

            return line[anchor_end:i]

    def get_id(self):
        id = ''
        for i in range(1, self.level + 1):
            if i > 1:
                id = id + '.'
            id = id + str(getattr(self.cur_id[i], 'get')())

        return id

    def replace_anchor(self, anchor, buf):
        anchor_str = ANCHOR_PREFIX + anchor + ANCHOR_SUFFIX
        buf = buf.replace(anchor_str, '')
        ref_str = REF_PREFIX + anchor + REF_SUFFIX
        id = self.get_id()
        buf = buf.replace(ref_str, id)

        return buf

    def post_proc(self, buf):
        """
        remove all empty lines
        replace '---' to line breaks
        """
        lines = []
        for line in buf.splitlines():
            if not line.strip():
                continue
            if not line.strip(LINE_BREAK):
                lines.append('\n')
                continue
            lines.append(line + '\n')
        return lines

    def proc_file(self):

        buf = ''
        with file(self.filename, 'r') as f:
            buf = f.read()
            f.seek(0)
            for line in f:
                level = self.check_level(line)
                if level is None:
                    continue

                if level == self.level:
                    self.cur_id[level].inc()
                elif level < self.level:
                    self.cur_id[level].inc()
                    for l in range(level + 1, self.level + 1):
                        self.cur_id[self.level].reset()
                else:
                    self.cur_id[level].reset()
                    self.cur_id[level].inc()

                self.level = level

                anchor = self.check_anchor(line)
                if not anchor:
                    continue
                buf = self.replace_anchor(anchor, buf)

        lines = self.post_proc(buf)
        with file(self.filename + '.out', 'w+') as f_out:
            f_out.writelines(lines)


def main(argv):
    if len(argv) < 2:
        print "wikiref.py <input file>"
        exit(0)

    input_file = argv[1]

    wikiref = WikiRef(input_file)
    wikiref.proc_file()


if __name__ == '__main__':
    main(sys.argv)
