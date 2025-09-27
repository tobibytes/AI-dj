"use client"
import { Turntable } from "@/components/turn-table";
import { useRef } from "react";

export default function Home() {
  const track1Ref = useRef<HTMLAudioElement | null>(null)
  const track2Ref = useRef<HTMLAudioElement | null>(null)

  const toggleTrack1 = () => {
    const audio = track1Ref.current
    if (!audio) return
    if (audio.paused) {
        audio.play().catch(() => {
            /* autoplay blocked or error */
        })
    } else {
        audio.pause()
        console.log(audio.currentTime)
    }
  }

  const toggleTrack2 = () => {
    const audio = track2Ref.current
    if (!audio) return
    if (audio.paused) {
        audio.play().catch(() => {
            /* autoplay blocked or error */
        })
    } else {
        audio.pause()
        console.log(audio.currentTime)
    }
  }

  return (
      
      <main className="container mx-auto px-4 py-8">
        <div className="flex flex-col lg:flex-row items-start justify-center gap-8">
          {/* Left Turntable */}
          <div className="flex-1 max-w-md">
            <Turntable side="left" trackName="99" artist="Olamide, Seyi Vibez, Asake, Young John ft. Daecolm" togglePlay={toggleTrack1} audioRef={track1Ref} track="https://rr3---sn-uhvcpax0n5-jbnz.googlevideo.com/videoplayback?expire=1758993246&ei=_sbXaKnnMOW1kucPp7m7IA&ip=2607%3Afb90%3Aeade%3A8b6b%3A8f3%3A678c%3Ae3fd%3Af6b6&id=o-ABQlbdz8ME-SLYjfwOILcQpGveATbZLiBA9LOlUnUOE0&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=0&met=1758971646%2C&mh=6G&mm=31%2C29&mn=sn-uhvcpax0n5-jbnz%2Csn-p5qlsn76&ms=au%2Crdu&mv=m&mvi=3&pl=44&rms=au%2Cau&gcr=us&initcwndbps=692500&bui=ATw7iSUUOG9m7Jraf6LE1nBJMT9MmEBbsxMa6LArLtuS52EWNaulS7cjzXdPNb5e1hOoTNLprKyLRtbA&vprv=1&svpuc=1&mime=audio%2Fwebm&ns=Mo3R9Bi17bTlbI_-Lt1tY7UQ&rqh=1&gir=yes&clen=4286063&dur=249.141&lmt=1749637660279898&mt=1758970657&fvip=2&keepalive=yes&lmw=1&fexp=51565116%2C51565682%2C51580970&c=TVHTML5&sefc=1&txp=4532534&n=ZvHBYeerguLing&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cgcr%2Cbui%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRQIgI8-l0AfvjE-MQSY1ieD-agWnEP_E5FrMv_jz1FAWDwsCIQDDNM5tyiOCCtSh-NPSui4LPaEUHyKfTErmvLr9vntnxA%3D%3D&sig=AJfQdSswRQIhAIo_ThNHdi4jjMU1VIUdV3D-VwN1e8rTxnrHxEc8ypSgAiBFOhAvdO6MALgoRdBUVqioKsj639mibblpMTEbAVQ3nw%3D%3D"/>
          </div>

      

          {/* Right Turntable */}
          <div className="flex-1 max-w-md">
            <Turntable  side="right" trackName="Alone" artist="FOLA & Bhadboi OML" togglePlay={toggleTrack2} audioRef={track2Ref} track="https://rr4---sn-uhvcpax0n5-jbnz.googlevideo.com/videoplayback?expire=1758992659&ei=s8TXaMCVLZrikucP4sit-QM&ip=2607%3Afb90%3Aeade%3A8b6b%3A8f3%3A678c%3Ae3fd%3Af6b6&id=o-ANFWqqfDVnVOnuO-ZDJiaTcKromSBxEDKFLJuQgmiHwP&itag=251&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&cps=0&met=1758971059%2C&mh=9b&mm=31%2C29&mn=sn-uhvcpax0n5-jbnz%2Csn-p5qlsndk&ms=au%2Crdu&mv=m&mvi=4&pl=44&rms=au%2Cau&initcwndbps=692500&bui=ATw7iSVn05rZnhq61UlJf07L95XGYc0lSLr09dDQlsIZGdU0cBok_jyFEY3v4zKhlnWuuzyRDUwnWxCA&vprv=1&svpuc=1&mime=audio%2Fwebm&ns=ptcKcmNRQ4U6ClBEiCzfljsQ&rqh=1&gir=yes&clen=2781132&dur=153.241&lmt=1731522591914492&mt=1758970657&fvip=1&keepalive=yes&lmw=1&fexp=51565116%2C51565681%2C51580970&c=TVHTML5&sefc=1&txp=4532434&n=WNNFcMBd9IK7Sg&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cxpc%2Cbui%2Cvprv%2Csvpuc%2Cmime%2Cns%2Crqh%2Cgir%2Cclen%2Cdur%2Clmt&lsparams=cps%2Cmet%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRQIgGdAGrNz0EkQ7o1o7MlvwZtXLw4eEoCKaDifYF9b0S3cCIQCJjNDXiyNTvs_lE8MAoff3F3CdZEYmjcuxknBg8C_o8A%3D%3D&sig=AJfQdSswRQIgVyVR-DwLqHGbId0txGegpjJl_FD0VrqAmM9wB9hFBQECIQCQ0tpLp938fgi0JYyc9-HEcFzB1wFupGvSUzKIVgxaEA%3D%3D"/>
          </div>
        </div>

    
      </main>
  );
}
