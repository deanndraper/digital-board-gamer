#!/bin/bash
# Run this on your Mac from Terminal
cd "/Users/deandraper/Documents/Claude/Digital Board Gamer"
mkdir -p transcripts
source ytdlp_env/bin/activate

yt-dlp --write-auto-subs --sub-lang en --skip-download --write-info-json \
  -o "transcripts/%(id)s" \
  "https://www.youtube.com/watch?v=Ldj-tDJRM6I" \
  "https://www.youtube.com/watch?v=57EfEW6ypS8" \
  "https://www.youtube.com/watch?v=scCdh7ioBMs" \
  "https://www.youtube.com/watch?v=e1mWGl02qGc" \
  "https://www.youtube.com/watch?v=36GJY-t4Wsk" \
  "https://www.youtube.com/watch?v=3kM8alH797U" \
  "https://www.youtube.com/watch?v=SqPYtFKbLWc" \
  "https://www.youtube.com/watch?v=Cjx5ywxxXho" \
  "https://www.youtube.com/watch?v=DTq_LCTWKwc" \
  "https://www.youtube.com/watch?v=wMUau9WZudM" \
  "https://www.youtube.com/watch?v=fyf7YwHVB5I" \
  "https://www.youtube.com/watch?v=NPk92-UGFUI" \
  "https://www.youtube.com/watch?v=2BiVEshPoGY" \
  "https://www.youtube.com/watch?v=Y9LBdp7HNvQ" \
  "https://www.youtube.com/watch?v=4t9n6aAB3Fs" \
  "https://www.youtube.com/watch?v=3TidXa-5hxE" \
  "https://www.youtube.com/watch?v=-I3l_wd53as" \
  "https://www.youtube.com/watch?v=ojd0i1xK3OE" \
  "https://www.youtube.com/watch?v=dxfnmqkZWr8" \
  "https://www.youtube.com/watch?v=LDFmYLIESsk" \
  "https://www.youtube.com/watch?v=zSOobj-Qv_A" \
  "https://www.youtube.com/watch?v=RQD7htbyEog" \
  "https://www.youtube.com/watch?v=ey6rkh8S_4o" \
  "https://www.youtube.com/watch?v=T_8B3dklxsU" \
  "https://www.youtube.com/watch?v=8yx3vTV9aRY" \
  "https://www.youtube.com/watch?v=UKhTd1qdRIo" \
  "https://www.youtube.com/watch?v=fVmRqaElm8k" \
  "https://www.youtube.com/watch?v=q3MZbPZU288" \
  "https://www.youtube.com/watch?v=Hjyhmo-amQg" \
  "https://www.youtube.com/watch?v=MPSbfIcz7s0" \
  "https://www.youtube.com/watch?v=2OKhEVC2BzI" \
  "https://www.youtube.com/watch?v=kQv2Jh5z7c0" \
  "https://www.youtube.com/watch?v=z3UEJMwxlIQ" \
  "https://www.youtube.com/watch?v=EXcCmL3oh5o" \
  "https://www.youtube.com/watch?v=f8BPvtHRjOw" \
  "https://www.youtube.com/watch?v=YGeIaTTHXsw" \
  "https://www.youtube.com/watch?v=y8UpZTyVV5Y" \
  "https://www.youtube.com/watch?v=bT769ajhdWE" \
  "https://www.youtube.com/watch?v=vzI-w00kV-8" \
  "https://www.youtube.com/watch?v=gnZ9qyuI0VQ" \
  "https://www.youtube.com/watch?v=QJYNNdn6hVY" \
  "https://www.youtube.com/watch?v=1ZMQmIGI44o" \
  "https://www.youtube.com/watch?v=rdvG0IBfs9g" \
  "https://www.youtube.com/watch?v=3gISKGz-_Zc" \
  "https://www.youtube.com/watch?v=3idoJDMPdLs" \
  "https://www.youtube.com/watch?v=Jbdmo9OpSKw" \
  "https://www.youtube.com/watch?v=xONG_fzwCgA" \
  "https://www.youtube.com/watch?v=r7xsLXpnNcM"

echo "Done! Check transcripts/ folder"
ls transcripts/ | wc -l
