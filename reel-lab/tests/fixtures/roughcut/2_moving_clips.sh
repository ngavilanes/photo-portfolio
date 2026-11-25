#!/bin/bash
set -e
W=1080; H=608; FPS=30
cd "$1/clips"
ENC="-c:v libx264 -preset veryfast -crf 16 -pix_fmt yuv420p -r $FPS"
SKY(){ echo "gradients=s=${W}x${H}:c0=0xa9c4cc:c1=0xe6e9e4:x0=0:y0=0:x1=0:y1=$H:d=$1:r=$FPS"; }
BOX(){ echo "color=c=$1:s=$2x$3:r=$FPS:d=$4"; }   # colour, w, h, dur

# 1. Terminal: walker leaves, flashes white 2.0-2.2s
ffmpeg -v error -y -f lavfi -i "$(SKY 3)" -f lavfi -i "$(BOX 0x10181a 60 130 3)" -f lavfi -i "$(BOX white 60 130 3)" -filter_complex "
[0]drawbox=0:380:$W:230:0x8f9a96:fill,drawbox=150:0:70:380:0xd9cdb8:fill,drawbox=600:0:14:380:0x4a5558:fill,drawbox=990:0:14:380:0x4a5558:fill,
drawbox=0:330:$W:14:0x5b6a6e:fill,drawbox=40:430:330:60:0x1c2a2e:fill,drawbox=700:430:340:60:0x1c2a2e:fill,drawbox=260:300:90:130:0x10181a:fill[b];
[b][1]overlay=x='760-t*30':y=300:enable='not(between(t,2.0,2.2))'[c];
[c][2]overlay=x='760-t*30':y=300:enable='between(t,2.0,2.2)',zoompan=z='1+0.0006*on':d=1:s=${W}x${H}:fps=$FPS" -t 3 $ENC c1.mp4

# 4. Plane on apron, black circle grows at the end
ffmpeg -v error -y -f lavfi -i "$(SKY 2)" -f lavfi -i "$(BOX 0xf2f4f2 520 60 2)" -f lavfi -i "$(BOX 0xb01c28 70 60 2)" -f lavfi -i "$(BOX 0x6a7478 420 6 2)" -filter_complex "
[0]drawbox=0:360:$W:250:0x9aa6a2:fill,drawbox=0:372:$W:6:0xd8c060:fill[b];
[b][1]overlay=x='80+t*60':y=300[c];[c][2]overlay=x='500+t*60':y=250[d];[d][3]overlay=x='120+t*60':y=322,
geq=r='r(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(T-1.5)*700))':g='g(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(T-1.5)*700))':b='b(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(T-1.5)*700))'" -t 2 $ENC c4.mp4

# 5. Plane front: circle opens, woman walks in (1.0s), jet-bridge inset grows (1.8s)
ffmpeg -v error -y -f lavfi -i "gradients=s=${W}x${H}:c0=0x7e9a94:c1=0xa9bdb6:x0=0:y0=0:x1=0:y1=$H:d=3:r=$FPS" \
 -f lavfi -i "gradients=s=420x300:c0=0x303a3c:c1=0xb0bcc0:x0=0:y0=0:x1=420:y1=0:d=3:r=$FPS" \
 -f lavfi -i "$(BOX 0x0c1214 110 85 3)" -f lavfi -i "$(BOX 0xe2dfd8 100 150 3)" -f lavfi -i "$(BOX 0xd8b070 50 90 3)" -filter_complex "
[0]drawbox=0:420:$W:188:0x6f827c:fill,drawbox=380:160:320:260:0xe4ece9:fill,drawbox=470:210:140:30:0x1c2428:fill,drawbox=0:260:1080:34:0xd0dcd8:fill,
drawbox=60:300:150:150:0x1d4a78:fill,drawbox=870:300:150:150:0x1d4a78:fill,drawbox=80:320:110:110:0x0c1214:fill,drawbox=890:320:110:110:0x0c1214:fill,drawbox=950:40:50:180:0x5f7f86:fill[bg];
[1]drawbox=0:0:420:30:0x10181a:fill,drawbox=0:270:420:30:0x10181a:fill,drawbox=190:80:50:150:0x0c1214:fill,drawbox=0:0:420:300:0x0c1214:t=8,
scale=w='max(2,min(420,(n/30-1.8)*500))':h='max(2,min(300,(n/30-1.8)*360))':eval=frame[ins];
[bg][2]overlay=x='520-t*10':y=170:enable='gte(t,1.0)'[a];[a][3]overlay=x='528-t*10':y=255:enable='gte(t,1.0)'[b2];
[b2][4]overlay=x='515-t*10':y=250:enable='gte(t,1.0)'[w];
[w][ins]overlay=x='(W-w)/2':y='(H-h)/2':enable='gte(t,1.8)',
geq=r='r(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(0.5-T)*1300))':g='g(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(0.5-T)*1300))':b='b(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(0.5-T)*1300))'" -t 3 $ENC c5.mp4

# 6. Bench silhouette + taxiing plane
ffmpeg -v error -y -f lavfi -i "$(SKY 0.5)" -f lavfi -i "$(BOX 0xf0f0f0 130 14 0.5)" -filter_complex "
[0]drawbox=0:380:$W:228:0x8a958c:fill,drawbox=760:230:50:150:0x7d8a88:fill[b];
[b][1]overlay=x='420+t*60':y=350,drawbox=0:120:260:488:0x0a0e10:fill" -t 0.5 $ENC c6.mp4
echo fixed
