"use client"
import { Turntable } from "@/components/turn-table";
import { DJMixer } from "@/components/dj-mixer";
import { Button } from "@/components/ui/button";
import { useRef, useState } from "react";

export default function Home() {
  const track1Ref = useRef<HTMLAudioElement | null>(null);
  const track2Ref = useRef<HTMLAudioElement | null>(null);

  const [crossfader, setCrossfader] = useState(50);

  // Equal-power volume mapping for both decks from crossfader position t [0..1]
  const updateVolumes = (t: number) => {
    const a = track1Ref.current;
    const b = track2Ref.current;
    if (!a && !b) return;
    const left = Math.cos((t * Math.PI) / 2);  // Deck A
    const right = Math.sin((t * Math.PI) / 2); // Deck B
    if (a) a.volume = left;
    if (b) b.volume = right;
  };

  const handleCrossfaderChange = (value: number) => {
    setCrossfader(value);
    updateVolumes(value / 100);
  };

  // Crossfade actions (no useEffect) -----------------------------------------
  const fadeRAF = useRef<number | null>(null);

  const cancelFade = () => {
    if (fadeRAF.current != null) {
      cancelAnimationFrame(fadeRAF.current);
      fadeRAF.current = null;
    }
  };

  // target: 0 (Deck A) or 1 (Deck B)
  const fadeTo = (target: 0 | 1, durationMs = 2000) => {
    cancelFade();
    const start = crossfader / 100;
    const end = target;
    const startTime = performance.now();
    const step = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      const value = start + (end - start) * progress;
      setCrossfader(Math.round(value * 100));
      updateVolumes(value);
      if (progress < 1) {
        fadeRAF.current = requestAnimationFrame(step);
      } else {
        fadeRAF.current = null;
      }
    };
    fadeRAF.current = requestAnimationFrame(step);
  };

  const fadeToA = () => fadeTo(0);
  const fadeToB = () => fadeTo(1);
  const cutToA = () => {
    cancelFade();
    setCrossfader(0);
    updateVolumes(0);
  };
  const cutToB = () => {
    cancelFade();
    setCrossfader(1);
    updateVolumes(1);
  };

  // Existing deck play/pause controls ----------------------------------------
  const toggleTrack1 = () => {
    const audio = track1Ref.current;
    updateVolumes(crossfader / 100);
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {
        /* autoplay blocked or error */
      });
    } else {
      audio.pause();
      console.log(audio.currentTime);
    }
  };

  const toggleTrack2 = () => {
    const audio = track2Ref.current;
    updateVolumes(crossfader / 100);
    if (!audio) return;
    if (audio.paused) {
      audio.play().catch(() => {
        /* autoplay blocked or error */
      });
    } else {
      audio.pause();
      console.log(audio.currentTime);
    }
  };

  return (
    <main className="container mx-auto px-4 py-8">
      <div className="flex flex-col lg:flex-row items-start justify-center gap-8">
        {/* Left Turntable */}
        <div className="flex-1 max-w-md">
          <Turntable
            side="left"
            trackName="99"
            artist="Olamide, Seyi Vibez, Asake, Young John ft. Daecolm"
            togglePlay={toggleTrack1}
            audioRef={track1Ref}
            track="https://rr3---sn-uhvcpax0n5-jbnz.googlevideo.com/videoplayback?expire=1758993246&ei=_sbXaKnnMOW1kucPp7m7IA&ip=2607%3Afb90%3Aeade%3A8b6b%3A8f3%3A678c%3Ae3fd%3Af6b6&id=o-ABQlbdz8ME-SLYjfwOILcQpGveATbZLiBA9LOlUnUOE0&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=0&met=1758971646%2C&mh=6G&mm=31%2C29&mn=sn-uhvcpax0n5-jbnz%2Csn-p5qlsn76&ms=au%2Crdu&mv=m&mvi=3&pl=44&rms=au%2Cau&gcr=us&initcwndbps=692500&bui=ATw7iSUUOG9m7Jraf6LE1nBJMT9MmEBbsxMa6LArLtuS52EWNaulS7cjzXdPNb5e1hOoTNLprKyLRtbA&vprv=1&svpuc=1&mime=audio%2Fwebm&ns=Mo3R9Bi17bTlbI_-Lt1tY7UQ&rqh=1&gir=yes&clen=4286063&dur=249.141&lmt=1749637660279898&mt=1758970657&fvip=2&keepalive=yes&lmw=1&fexp=51565116%2C51565682%2C51580970&c=TVHTML5&sefc=1&txp=4532534&n=ZvHBYeerguLing&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cbui%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRQIgI8-l0AfvjE-MQSY1ieD-agWnEP_E5FrMv_jz1FAWDwsCIQDDNM5tyiOCCtSh-NPSui4LPaEUHyKfTErmvLr9vntnxA%3D%3D&sig=AJfQdSswRQIhAIo_ThNHdi4jjMU1VIUdV3D-VwN1e8rTxnrHxEc8ypSgAiBFOhAvdO6MALgoRdBUVqioKsj639mibblpMTEbAVQ3nw%3D%3D"
          />
        </div>

        {/* Right Turntable */}
        <div className="flex-1 max-w-md">
          <Turntable
            side="right"
            trackName="Escaladizzy"
            artist="Mavo ft Wave$tar"
            togglePlay={toggleTrack2}
            audioRef={track2Ref}
            track="https://rr5---sn-uhvcpax0n5-jbns.googlevideo.com/videoplayback?expire=1759002251&ei=K-rXaO3CCdODkucP_P262AE&ip=2607%3Afb90%3Aeade%3A8b6b%3A8f3%3A678c%3Ae3fd%3Af6b6&id=o-AMgruXNlAwQl2PPQBM7wp291nCsGKMO8vv6hxlEl_qCd&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=0&met=1758980651%2C&mh=W6&mm=31%2C29&mn=sn-uhvcpax0n5-jbns%2Csn-p5qs7nzk&ms=au%2Crdu&mv=m&mvi=5&pl=44&rms=au%2Cau&initcwndbps=747500&bui=ATw7iSWipEvDcpvvjsVLd-WGdZu5D5isnGF2ZSCZhBz7mgxJERxFEp4iaTGdoXPcqecsmG54W5oLh-Yf&vprv=1&svpuc=1&mime=audio%2Fwebm&ns=fn7RV29Q0XsbahAyM-9r7jUQ&rqh=1&gir=yes&clen=2728843&dur=172.621&lmt=1750923463784531&mt=1758980266&fvip=5&keepalive=yes&lmw=1&fexp=51565115%2C51565682%2C51580970&c=TVHTML5&sefc=1&txp=5532534&n=yg7jSLbRHc77zw&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRgIhAOcsIHvTb0DFUIgtTH9__aj1LTP53KtYHHW3N8HQqupgAiEAvkvdSOQlav-LyONTRzAYHKk2oC3v4-rM0-mWJYrM4i4%3D&sig=AJfQdSswRgIhAMy1AoWtn92_c9aZSCfnzbUvmE_olCgPXjA80vfzdSePAiEA3wWzbm2--s06JlnXF_kMuV9jTnvZIKE4ExQrW8YgD6A%3D"
          />
        </div>
      </div>

      <div className="mt-8 space-y-4">
        <DJMixer crossfader={crossfader} onCrossfaderChange={handleCrossfaderChange} />
        <div className="flex flex-wrap gap-2 justify-center" aria-label="AI Actions">
          <Button data-action="fade-to-a" variant="outline" onClick={fadeToA}>
            Fade to Deck A (2s)
          </Button>
          <Button data-action="fade-to-b" variant="outline" onClick={fadeToB}>
            Fade to Deck B (2s)
          </Button>
          <Button data-action="cut-to-a" variant="secondary" onClick={cutToA}>
            Cut to Deck A
          </Button>
          <Button data-action="cut-to-b" variant="secondary" onClick={cutToB}>
            Cut to Deck B
          </Button>
        </div>
      </div>
    </main>
  );
}
