import React from "react";
import {
  AbsoluteFill, Audio, Composition, Easing, Img, interpolate, OffthreadVideo, Series, Sequence,
  staticFile, useCurrentFrame, useVideoConfig,
} from "remotion";
import { loadFont as loadCinzel } from "@remotion/google-fonts/Cinzel";
import { loadFont as loadSpectral } from "@remotion/google-fonts/Spectral";

const { fontFamily: CINZEL } = loadCinzel("normal", { weights: ["600", "700"] });
const { fontFamily: SPECTRAL } = loadSpectral("normal", { weights: ["400", "500"] });
const GOLD = "#dcaa66", PALE = "#f0d3a2", INK = "#0c0704";

// Narasi (en-US-AvaMultilingualNeural) & adegan: durasi adegan = durasi suara + jeda
const SCENES = [
  { id: "s1", vo: 4.9, kind: "video", src: "f/hero.mp4", trim: 0.5, kicker: "Indonesian dance", head: "Knowledge held in the body", text: "Every Indonesian dance carries centuries of knowledge, held in the body." },
  { id: "s2", vo: 4.44, kind: "video", src: "f/arena_panggung.mp4", trim: 0.5, kicker: "NaraMotion", head: "Movement becomes 3D data", text: "NaraMotion turns those movements into living, three-dimensional data." },
  { id: "s3", vo: 7.49, kind: "video", src: "f/arena_borobudur.mp4", trim: 0, rate: 0.82, zoom: [1.35, 1.5], fy: 0.62, kicker: "2,568 clips · SAM 3D Body", head: "Digitised to the fingertips", text: "Two thousand five hundred and sixty-eight Balinese dance clips, digitised in 3D, down to the fingertips." },
  { id: "s4", vo: 6.72, kind: "video", src: "f/arena_trowulan.mp4", trim: 0, rate: 0.88, zoom: [1.45, 1.6], fy: 0.66, kicker: "Arena Tari", head: "Dance it anywhere", text: "Watch them come alive anywhere: on a golden stage, or before the stupas of Borobudur." },
  { id: "s5", vo: 8.52, kind: "screen", src: "f/kelas_kalibrasi.mp4", trim: 9, kicker: "Kamera AI", head: "Calibrate, then score in 3D", text: "Then practise. Our camera AI checks your light, distance and posture first, then scores every joint in 3D." },
  { id: "s6", vo: 4.15, kind: "screen", src: "f/kelas_duo.mp4", trim: 0, kicker: "Multi-dancer", head: "Up to four dancers", text: "Dancing together? It follows up to four dancers at once." },
  { id: "s7", vo: 4.9, kind: "phone", src: "f/reels.mp4", trim: 0, kicker: "Reels · Sejarah", head: "Keep tradition moving", text: "Scroll real dancers, learn the history, and keep tradition moving." },
  { id: "s8", vo: 2.86, kind: "end", text: "NaraMotion. Dance, preserved." },
] as const;
const PAD = 0.9, FPS = 30;
const sceneFrames = (s: { vo: number }) => Math.round((s.vo + PAD) * FPS);
const TOTAL = SCENES.reduce((a, s) => a + sceneFrames(s), 0) + Math.round(1.6 * FPS);

export const MyComposition = () => (
  <Composition id="NaraAd" component={NaraAd} durationInFrames={TOTAL} fps={FPS} width={1920} height={1080} />
);

const ease = Easing.bezier(0.16, 1, 0.3, 1);

const Title: React.FC<{ kicker: string; head: string; w?: number; size?: number }> = ({ kicker, head, w = 1100, size = 96 }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  return (
    <div style={{ position: "absolute", left: 120, top: 110, maxWidth: w }}>
      <div style={{ fontFamily: SPECTRAL, fontSize: 30, letterSpacing: "0.22em", textTransform: "uppercase", color: GOLD,
        opacity: interpolate(frame, [0.2 * fps, 0.8 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{kicker}</div>
      <div style={{ fontFamily: CINZEL, fontWeight: 700, fontSize: size, lineHeight: 1.05, color: PALE, marginTop: 14, textShadow: "0 6px 30px rgba(0,0,0,.85)",
        opacity: interpolate(frame, [0.35 * fps, 1.0 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        translate: interpolate(frame, [0.35 * fps, 1.1 * fps], ["0px 40px", "0px 0px"], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }) }}>{head}</div>
      <div style={{ height: 4, background: GOLD, marginTop: 22, borderRadius: 2,
        width: interpolate(frame, [0.6 * fps, 1.4 * fps], [0, 260], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }) }} />
    </div>
  );
};

const Caption: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  return (
    <div style={{ position: "absolute", left: 160, right: 160, bottom: 90, textAlign: "center", fontFamily: SPECTRAL, fontWeight: 500, fontSize: 44, lineHeight: 1.3,
      color: "#fff7e8", textShadow: "0 3px 14px rgba(0,0,0,.95)",
      opacity: interpolate(frame, [0.15 * fps, 0.5 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{text}</div>
  );
};

const Fade: React.FC<{ dur: number; children: React.ReactNode }> = ({ dur, children }) => {
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{ opacity: interpolate(frame, [0, 9, dur - 9, dur], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>{children}</AbsoluteFill>;
};

const VideoScene: React.FC<{ s: (typeof SCENES)[number] & { kind: "video" }; dur: number }> = ({ s, dur }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  const z = "zoom" in s && s.zoom ? s.zoom : [1.04, 1.12];
  const fy = "fy" in s && s.fy ? s.fy : 0.5;
  return (
    <Fade dur={dur}>
      <AbsoluteFill style={{ backgroundColor: INK, overflow: "hidden" }}>
        <OffthreadVideo src={staticFile(s.src)} trimBefore={Math.round(s.trim * fps)} playbackRate={"rate" in s && s.rate ? s.rate : 1} muted
          style={{ width: "100%", height: "100%", objectFit: "cover", transformOrigin: `50% ${fy * 100}%`,
            scale: interpolate(frame, [0, dur], [z[0], z[1]], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} />
        <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(12,7,4,.72) 0%, rgba(12,7,4,.05) 38%, rgba(12,7,4,.08) 62%, rgba(12,7,4,.82) 100%)" }} />
        <Title kicker={s.kicker} head={s.head} />
        <Caption text={s.text} />
      </AbsoluteFill>
    </Fade>
  );
};

const PhoneScene: React.FC<{ s: (typeof SCENES)[number] & { kind: "phone" }; dur: number }> = ({ s, dur }) => {
  const frame = useCurrentFrame();
  return (
    <Fade dur={dur}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 70% 40%, #3a1a10 0%, ${INK} 70%)` }}>
        <div style={{ position: "absolute", right: 260, top: 110, width: 486, height: 864, borderRadius: 54, overflow: "hidden", border: "10px solid #2c1b0f",
          boxShadow: "0 30px 90px rgba(0,0,0,.7)", rotate: interpolate(frame, [0, dur], ["-2deg", "1deg"]) }}>
          <OffthreadVideo src={staticFile(s.src)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
        <Title kicker={s.kicker} head={s.head} />
        <div style={{ position: "absolute", left: 120, top: 460, width: 820, fontFamily: SPECTRAL, fontSize: 46, lineHeight: 1.35, color: "#fff7e8" }}>{s.text}</div>
      </AbsoluteFill>
    </Fade>
  );
};

const ScreenScene: React.FC<{ s: (typeof SCENES)[number] & { kind: "screen" }; dur: number }> = ({ s, dur }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  return (
    <Fade dur={dur}>
      <AbsoluteFill style={{ background: `radial-gradient(ellipse at 72% 45%, #33170e 0%, ${INK} 72%)` }}>
        <div style={{ position: "absolute", right: 70, top: 260, width: 1060, height: 596, borderRadius: 26, overflow: "hidden", border: "2px solid rgba(220,170,102,.35)",
          boxShadow: "0 40px 110px rgba(0,0,0,.75)", scale: interpolate(frame, [0, dur], [0.97, 1.02], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
          translate: interpolate(frame, [0, 0.8 * fps], ["0px 40px", "0px 0px"], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }) }}>
          <OffthreadVideo src={staticFile(s.src)} trimBefore={Math.round(s.trim * fps)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} />
        </div>
        <Title kicker={s.kicker} head={s.head} w={600} size={70} />
        <div style={{ position: "absolute", left: 120, top: 520, width: 560, fontFamily: SPECTRAL, fontSize: 40, lineHeight: 1.35, color: "#fff7e8" }}>{s.text}</div>
      </AbsoluteFill>
    </Fade>
  );
};

const EndCard: React.FC<{ dur: number }> = ({ dur }) => {
  const frame = useCurrentFrame(); const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ background: `radial-gradient(ellipse at 50% 42%, #2a120c 0%, ${INK} 68%)`, alignItems: "center", justifyContent: "center" }}>
      <Img src={staticFile("naramotion-logo.png")} style={{ width: 560,
        opacity: interpolate(frame, [0, 0.8 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        scale: interpolate(frame, [0, dur], [0.94, 1.02], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: ease }) }} />
      <div style={{ fontFamily: CINZEL, fontSize: 52, color: PALE, marginTop: 10, letterSpacing: "0.06em",
        opacity: interpolate(frame, [0.8 * fps, 1.5 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>Dance, preserved.</div>
      <div style={{ fontFamily: SPECTRAL, fontSize: 40, color: GOLD, marginTop: 26,
        opacity: interpolate(frame, [1.3 * fps, 2 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }}>naramotion.web.app</div>
      <div style={{ position: "absolute", bottom: 46, fontFamily: SPECTRAL, fontSize: 22, color: "#9c8b70", textAlign: "center", maxWidth: 1500, lineHeight: 1.4 }}>
        Dance data: Hendrawan et al., Mendeley Data (CC BY 4.0) · 3D: SAM 3D Body (Meta) · Characters: Adobe Mixamo · Arenas: Sketchfab (CC BY 4.0) · Music: Gamelan Djoged, 1931 (public domain)
      </div>
    </AbsoluteFill>
  );
};

const Music: React.FC = () => {
  const frame = useCurrentFrame();
  return <Audio src={staticFile("music.mp3")} volume={interpolate(frame, [0, 30, TOTAL - 60, TOTAL], [0, 0.24, 0.24, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })} />;
};

export const NaraAd: React.FC = () => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: INK }}>
      <Music />
      <Series>
        {SCENES.map((s) => {
          const dur = sceneFrames(s) + (s.kind === "end" ? Math.round(1.6 * fps) : 0);
          return (
            <Series.Sequence key={s.id} durationInFrames={dur} name={s.id}>
              <Sequence from={Math.round(0.35 * fps)}><Audio src={staticFile(`vo/${s.id}.mp3`)} volume={1} /></Sequence>
              {s.kind === "video" && <VideoScene s={s} dur={dur} />}
              {s.kind === "phone" && <PhoneScene s={s} dur={dur} />}
              {s.kind === "screen" && <ScreenScene s={s} dur={dur} />}
              {s.kind === "end" && <EndCard dur={dur} />}
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
