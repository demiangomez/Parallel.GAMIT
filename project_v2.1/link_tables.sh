#!/bin/bash
            # set up links
            cd /Users/gomez.124/mounts/qnap/ign/procesamientos/gamit/2003/002/igs-sirgas/tables;
            sh_links.tables -frame J2000 -year 2003 -eop usno -topt none &> sh_links.out;
            # ln -s rmsc.apr lfile.
            cd ..;
            