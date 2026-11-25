#!/bin/bash
set -e
cd "$1"
ffmpeg -v error -y \
 -i clips/c1.mp4 -i clips/c2.mp4 -i clips/c3.mp4 -i clips/c4.mp4 -i clips/c5.mp4 -i clips/c6.mp4 -i clips/c7.mp4 \
 -f lavfi -i "color=c=black:s=1500x230:r=30:d=14.5" \
 -f lavfi -i "aevalsrc='0.9*sin(2*PI*52*t)*exp(-9*mod(t,0.5))+0.25*sin(2*PI*1800*t)*exp(-60*mod(t+0.25,0.5))':d=14.5:s=44100" \
 -filter_complex "
[0][1][2][3][4][5][6]concat=n=7:v=1:a=0[v];
[7]drawtext=fontfile='${FONT:-/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf}':text='AIRPORTS':fontsize=215:fontcolor=0xc01820:x=(w-text_w)/2:y=(h-text_h)/2-10,scale=640:230,pad=1080:608:220:60:black,format=yuv420p[t0];
[t0]format=gbrp,split[ta][tb];[tb]gblur=sigma=9[tg];[ta][tg]blend=all_mode=lighten[title];
[v]format=gbrp,colorbalance=rs=-0.10:gs=0.05:bs=0.12:rm=-0.12:gm=0.06:bm=0.08:rh=-0.06:bh=0.04,
   curves=all='0/0.06 0.5/0.5 1/0.94',eq=saturation=0.72:contrast=1.06,format=gbrp[g];
[title]colorkey=black:0.2:0.25[tk];[g][tk]overlay=enable='between(t,0.5,3.0)'[gt];
[gt]format=gbrp,split[ga][gb];[gb]gblur=sigma=14,eq=brightness=-0.05[gbl];[ga][gbl]blend=all_mode=screen:all_opacity=0.18[gl];
[gl]noise=alls=4:allf=t,format=yuv420p,pad=1080:1920:0:(oh-ih)/2:black,fade=t=out:st=12.4:d=2.1[vo]
" -map "[vo]" -map 8:a -t 14.5 -c:v libx264 -preset medium -crf 21 -pix_fmt yuv420p -c:a aac -b:a 160k -af "afade=t=out:st=12.8:d=1.7" airports_roughcut.mp4
