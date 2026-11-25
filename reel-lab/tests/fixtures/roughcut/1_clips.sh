#!/bin/bash
# Procedural stand-in footage + rough cut in the style of the "Airports" reel.
set -e
W=1080; H=608; FPS=30
O="$1"; mkdir -p "$O/clips"; cd "$O/clips"
ENC="-c:v libx264 -preset veryfast -crf 16 -pix_fmt yuv420p -r $FPS"
sky="gradients=s=${W}x${H}:c0=0xa9c4cc:c1=0xe6e9e4:x0=0:y0=0:x1=0:y1=$H:d=%s:r=$FPS"

# 1. Terminal (0-3.0s): window, mullions, bench silhouettes, walker who flashes white at 2.0s
ffmpeg -v error -y -f lavfi -i "$(printf "$sky" 3.0)" -vf "
drawbox=0:380:$W:230:0x8f9a96:fill,
drawbox=150:0:70:380:0xd9cdb8:fill,drawbox=600:0:14:380:0x4a5558:fill,drawbox=990:0:14:380:0x4a5558:fill,
drawbox=0:330:$W:14:0x5b6a6e:fill,
drawbox=40:430:330:60:0x1c2a2e:fill,drawbox=700:430:340:60:0x1c2a2e:fill,
drawbox=260:300:90:130:0x10181a:fill,
drawbox='760-t*30':300:60:130:0x10181a:fill:enable='lt(t,2.0)',
drawbox='700-t*30':300:60:130:white:fill:enable='between(t,2.0,2.2)',
drawbox='700-t*30':300:60:130:0x10181a:fill:enable='gt(t,2.2)',
zoompan=z='1+0.0006*on':d=1:s=${W}x${H}:fps=$FPS" -t 3.0 $ENC c1.mp4

# 2. Vending machines (3.0-6.0): dense grid of coloured boxes, slow push
ffmpeg -v error -y -f lavfi -i "color=c=0x14181a:s=1500x850:d=3:r=$FPS" -vf "
$(for r in 0 1 2 3 4 5; do for c in 0 1 2 3 4 5 6 7 8 9 10 11; do
  col=$(printf '0x%02x%02x%02x' $(( (r*53+c*37)%180+60 )) $(( (r*91+c*29)%150+40 )) $(( (r*17+c*71)%140+40 )))
  printf "drawbox=%d:%d:90:100:%s:fill," $((30+c*120)) $((60+r*130)) $col; done; done)
drawbox=0:0:1500:50:0xb8202a:fill,
crop=${W}:${H}:'(iw-ow)/2+t*20':'(ih-oh)/2-t*8'" -t 3.0 $ENC c2.mp4

# 3. Low-angle pole shot (6.0-6.5): teal ceiling + diagonal bar
ffmpeg -v error -y -f lavfi -i "gradients=s=${W}x${H}:c0=0x2aa7b8:c1=0xcfeef0:x0=0:y0=0:x1=$W:y1=$H:d=0.5:r=$FPS" -vf "
geq=lum='lum(X,Y)':cb='cb(X,Y)':cr='cr(X,Y)',
drawbox=300:0:70:$H:0x8aa0a8:fill,drawbox=360:200:200:120:0x181c20:fill,
zoompan=z='1.15-0.0015*on':d=1:s=${W}x${H}:fps=$FPS" -t 0.5 $ENC c3.mp4

# 4. Plane on apron (6.5-8.5) ending in a black circle that grows (zoom-through)
ffmpeg -v error -y -f lavfi -i "$(printf "$sky" 2.0)" -vf "
drawbox=0:360:$W:250:0x9aa6a2:fill,drawbox=0:372:$W:6:0xd8c060:fill,
drawbox='80+t*60':300:520:60:0xf2f4f2:fill,drawbox='500+t*60':250:70:60:0xb01c28:fill,
drawbox='120+t*60':322:420:6:0x6a7478:fill,
geq=r='r(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(T-1.5)*700))':g='g(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(T-1.5)*700))':b='b(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(T-1.5)*700))'" -t 2.0 $ENC c4.mp4

# 5. Plane front (8.5-11.5): circle opens, woman walks in at 1.0s, jet-bridge inset grows at 1.8s
ffmpeg -v error -y -f lavfi -i "gradients=s=${W}x${H}:c0=0x7e9a94:c1=0xa9bdb6:x0=0:y0=0:x1=0:y1=$H:d=3:r=$FPS" \
 -f lavfi -i "gradients=s=420x300:c0=0x303a3c:c1=0xb0bcc0:x0=0:y0=0:x1=420:y1=0:d=3:r=$FPS" -filter_complex "
[0]drawbox=0:420:$W:188:0x6f827c:fill,
drawbox=380:160:320:260:0xe4ece9:fill,drawbox=470:210:140:30:0x1c2428:fill,
drawbox=0:260:1080:34:0xd0dcd8:fill,
drawbox=60:300:150:150:0x1d4a78:fill,drawbox=870:300:150:150:0x1d4a78:fill,
drawbox=80:320:110:110:0x0c1214:fill,drawbox=890:320:110:110:0x0c1214:fill,
drawbox=950:40:50:180:0x5f7f86:fill[bg];
[1]drawbox=0:0:420:30:0x10181a:fill,drawbox=0:270:420:30:0x10181a:fill,drawbox=190:80:50:150:0x0c1214:fill,
drawbox=0:0:420:300:0x0c1214:t=8[ins];
[bg]drawbox='420-t*10':170:110:85:0x0c1214:fill:enable='gte(t,1.0)',
drawbox='428-t*10':255:100:150:0xe2dfd8:fill:enable='gte(t,1.0)',
drawbox='415-t*10':250:50:90:0xd8b070:fill:enable='gte(t,1.0)'[w];
[ins]scale=w='max(2,min(420,(t-1.8)*500))':h='max(2,min(300,(t-1.8)*360))':eval=frame,format=yuv420p[s];
[w][s]overlay=x='(W-w)/2':y='(H-h)/2':enable='gte(t,1.8)',
geq=r='r(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(0.5-T)*1300))':g='g(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(0.5-T)*1300))':b='b(X,Y)*gt(hypot(X-W/2,Y-H/2),max(0,(0.5-T)*1300))'" -t 3.0 $ENC c5.mp4

# 6. Bench silhouette + taxiing plane (11.5-12.0 ... held to 12.0)
ffmpeg -v error -y -f lavfi -i "$(printf "$sky" 0.5)" -vf "
drawbox=0:380:$W:228:0x8a958c:fill,drawbox='420+t*60':350:130:14:0xf0f0f0:fill,drawbox=760:230:50:150:0x7d8a88:fill,
drawbox=0:120:260:488:0x0a0e10:fill" -t 0.5 $ENC c6.mp4

# 7. Sunset over wing (12.0-14.5), fades to black in last 2s
ffmpeg -v error -y -f lavfi -i "gradients=s=${W}x${H}:c0=0x3a2a5a:c1=0xf08a3c:x0=0:y0=0:x1=0:y1=$H:d=2.5:r=$FPS" -vf "
drawbox=0:420:$W:188:0x1c2036:fill,
geq=r='if(gt(X-700,(Y-120)*-0.35)*lt(Y,430)*lt(X-700,(430-Y)*0.2+80)*gt(X,700),12,r(X,Y))':g='if(gt(X-700,(Y-120)*-0.35)*lt(Y,430)*lt(X-700,(430-Y)*0.2+80)*gt(X,700),14,g(X,Y))':b='if(gt(X-700,(Y-120)*-0.35)*lt(Y,430)*lt(X-700,(430-Y)*0.2+80)*gt(X,700),22,b(X,Y))'" -t 2.5 $ENC c7.mp4
echo clips done
