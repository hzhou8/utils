#!/usr/bin/python

import sys
import tempfile
import subprocess
from shutil import copyfile

def commit_patch(msg, body):
    with tempfile.NamedTemporaryFile() as f:
        f.write(body)
        f.flush()
        if subprocess.call('git apply %s' % f.name, shell=True) != 0:
            copyfile(f.name, '/tmp/failed_patch')
            raise Exception("git apply failed")
        # TODO: escape special characters such as " ' in msg
        # TODO: handle new/deleted files
        subprocess.check_output('git add -u; git commit -m "%s"' % msg,
                                shell=True)


def check_out_branch(branch):
    subprocess.check_output('git checkout master', shell=True)
    subprocess.check_output('git pull origin master', shell=True)
    subprocess.check_output('git checkout -b review_%s' %
                            branch, shell=True)

def main(argv):
    if len(argv) < 2:
        print "patchwork_review.py <patches file>"
        exit(0)

    input_file = argv[1]

    state = 'START'
    title = ''
    commit_msg = ''
    patch_body = ''
    with file(input_file, 'r') as f:
        check_out_branch(f.name.rstrip('..patch'))
        for line in f:
            if state == 'START':
                # look for "Subject" and "[", possibly "]"
                if line.startswith('Subject:'):
                    state = 'TITLE_FOUND'
                    lsq = line.find('[')
                    if lsq >= 0:
                        rsq = line.find(']', lsq + 1)
                        if rsq > 0:

                            state = 'TITLE_STARTED'
                            title = line[rsq + 1:].strip()
                    else:
                        state = 'TITLE_STARTED'
                        title = line.lstrip('Subject:').strip()

            elif state == 'TITLE_FOUND':
                # look for "]"
                rsq = line.find(']')
                if rsq < 0:
                    raise Exception('"]" not found')
                state = 'TITLE_STARTED'
                title = line[rsq + 1:].strip()

            elif state == 'TITLE_STARTED':
                # look for "X-Patchwork"
                if line.startswith('X-Patchwork'):
                    state = 'TITLE_DONE'
                else:
                    title += '' + line

            elif state == 'TITLE_DONE':
                # look for "List-Id:"
                if line.startswith('List-Id:'):
                    state = 'CMT_MSG_STARTED'

            elif state == 'CMT_MSG_STARTED':
                if line.rstrip() == '---':
                    state = 'CMT_MSG_DONE'
                    commit_msg = title + commit_msg
                else:
                    commit_msg += line

            elif state == 'CMT_MSG_DONE':
                if line.startswith('From patchwork '):
                    state = 'START'
                    # commit current patch
                    commit_patch(commit_msg, patch_body)
                    title = ''
                    commit_msg = ''
                    patch_body = ''
                else:
                    patch_body += line

    # commit the last patch
    commit_patch(commit_msg, patch_body)


if __name__ == '__main__':
    main(sys.argv)
