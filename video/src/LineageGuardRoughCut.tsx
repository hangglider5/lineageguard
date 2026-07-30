import {Audio, Video} from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

const colors = {
  canvas: "#F7F9FC",
  white: "#FFFFFF",
  ink: "#11151D",
  muted: "#626A78",
  line: "#D9DEE7",
  blue: "#075EE6",
  blueSoft: "#EDF4FF",
  risk: "#C5161D",
  riskSoft: "#FFF1F1",
  success: "#118346",
};

const base: React.CSSProperties = {
  background: colors.canvas,
  color: colors.ink,
  fontFamily: "Inter, Arial, sans-serif",
};

const fade = (frame: number, duration: number) =>
  interpolate(frame, [0, 18, duration - 18, duration], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

const Eyebrow = ({children}: {children: React.ReactNode}) => (
  <div
    style={{
      color: colors.blue,
      fontSize: 28,
      fontWeight: 800,
      letterSpacing: "0.13em",
      textTransform: "uppercase",
    }}
  >
    {children}
  </div>
);

const Pill = ({children, tone = "blue"}: {children: React.ReactNode; tone?: "blue" | "risk" | "success"}) => {
  const palette =
    tone === "risk"
      ? {background: colors.riskSoft, color: colors.risk}
      : tone === "success"
        ? {background: "#EAF7EF", color: colors.success}
        : {background: colors.blueSoft, color: colors.blue};
  return (
    <span
      style={{
        ...palette,
        borderRadius: 999,
        padding: "12px 20px",
        fontSize: 28,
        fontWeight: 800,
        letterSpacing: "0.04em",
      }}
    >
      {children}
    </span>
  );
};

const Intro = () => {
  const frame = useCurrentFrame();
  const sourceScale = interpolate(frame, [0, 30], [0.94, 1], {
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });
  const graphProgress = interpolate(frame, [150, 420], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const loopOpacity = interpolate(frame, [450, 570], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const nodes = Array.from({length: 17});
  return (
    <AbsoluteFill style={{...base, padding: "92px 110px"}}>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
        <Eyebrow>LineageGuard</Eyebrow>
        <Pill tone="risk">PROPOSED DROP</Pill>
      </div>
      <div style={{display: "flex", flex: 1, alignItems: "center", gap: 96}}>
        <div style={{width: 700, display: "flex", flexDirection: "column", gap: 34}}>
          <h1 style={{fontSize: 92, lineHeight: 0.98, letterSpacing: "-0.055em", margin: 0}}>
            One column looks local.
          </h1>
          <div
            style={{
              alignSelf: "flex-start",
              scale: sourceScale,
              background: colors.white,
              border: `2px solid ${colors.line}`,
              borderRadius: 22,
              padding: "32px 38px",
              fontFamily: "SFMono-Regular, Consolas, monospace",
              fontSize: 35,
              boxShadow: "0 20px 60px rgba(17,21,29,0.08)",
            }}
          >
            orders.<span style={{color: colors.risk, textDecoration: "line-through"}}>order_total</span>
          </div>
          <div style={{opacity: loopOpacity, display: "flex", flexDirection: "column", gap: 18}}>
            <div style={{fontSize: 42, fontWeight: 800}}>Context → Decision → Validated Plan → Write-back</div>
            <Pill tone="success">✓ Read-back verified</Pill>
          </div>
        </div>
        <div style={{width: 880, height: 690, position: "relative"}}>
          <svg width="880" height="690" style={{position: "absolute", inset: 0}}>
            {nodes.map((_, index) => {
              const angle = (index / nodes.length) * Math.PI * 2;
              const x = 440 + Math.cos(angle) * (220 + (index % 3) * 45);
              const y = 345 + Math.sin(angle) * (170 + (index % 4) * 30);
              return (
                <line
                  key={index}
                  x1="440"
                  y1="345"
                  x2={x}
                  y2={y}
                  stroke={colors.blue}
                  strokeWidth="3"
                  opacity={graphProgress * 0.45}
                  strokeDasharray="9 12"
                />
              );
            })}
          </svg>
          <div
            style={{
              position: "absolute",
              left: 310,
              top: 245,
              width: 260,
              height: 200,
              background: colors.white,
              border: `3px solid ${colors.blue}`,
              borderRadius: 28,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              gap: 14,
              boxShadow: "0 24px 80px rgba(7,94,230,0.16)",
            }}
          >
            <strong style={{fontSize: 76, color: colors.blue}}>{Math.round(graphProgress * 17)}</strong>
            <span style={{fontSize: 26, color: colors.muted}}>downstream assets</span>
          </div>
          {nodes.map((_, index) => {
            const angle = (index / nodes.length) * Math.PI * 2;
            const radiusX = 220 + (index % 3) * 45;
            const radiusY = 170 + (index % 4) * 30;
            const x = 440 + Math.cos(angle) * radiusX - 42;
            const y = 345 + Math.sin(angle) * radiusY - 24;
            return (
              <div
                key={index}
                style={{
                  position: "absolute",
                  left: x,
                  top: y,
                  width: 84,
                  height: 48,
                  borderRadius: 12,
                  background: colors.white,
                  border: `2px solid ${colors.line}`,
                  opacity: graphProgress,
                  scale: interpolate(graphProgress, [0, 1], [0.75, 1]),
                }}
              />
            );
          })}
          <div style={{position: "absolute", right: 0, top: 30, opacity: graphProgress}}>
            <Pill tone="risk">BLOCK / HIGH</Pill>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const LiveReview = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{...base, padding: "70px 84px", opacity: fade(frame, 1440)}}>
      <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32}}>
        <div>
          <Eyebrow>Live DataHub MCP workflow</Eyebrow>
          <div style={{fontSize: 48, fontWeight: 850, marginTop: 8}}>Resolve → trace → validate</div>
        </div>
        <Pill tone="success">Read-only public surface</Pill>
      </div>
      <div
        style={{
          flex: 1,
          overflow: "hidden",
          borderRadius: 22,
          border: `2px solid ${colors.line}`,
          background: colors.white,
          boxShadow: "0 28px 90px rgba(17,21,29,0.14)",
        }}
      >
        <Video
          src={staticFile("captures/live-review.webm")}
          muted
          style={{width: "100%", height: "100%", objectFit: "cover"}}
        />
      </div>
    </AbsoluteFill>
  );
};

const Planner = () => {
  const frame = useCurrentFrame();
  const rows = [
    ["01", "dbt orders_by_customer", "update_transformation"],
    ["06", "Snowflake customer_360", "update_transformation"],
    ["12", "Looker orders", "update_semantic_model"],
    ["17", "Power BI revenue", "update_semantic_model"],
  ];
  return (
    <AbsoluteFill style={{...base, padding: "92px 110px", opacity: fade(frame, 1080)}}>
      <Eyebrow>Bounded DeepSeek planner</Eyebrow>
      <div style={{display: "grid", gridTemplateColumns: "1.3fr 0.7fr", gap: 70, flex: 1, alignItems: "center"}}>
        <div style={{display: "flex", flexDirection: "column", gap: 22}}>
          <h2 style={{fontSize: 78, lineHeight: 1, letterSpacing: "-0.045em", margin: "0 0 12px"}}>
            Platform-aware planning.<br />Deterministic boundaries.
          </h2>
          {rows.map(([sequence, asset, action], index) => (
            <div
              key={sequence}
              style={{
                display: "grid",
                gridTemplateColumns: "90px 1fr 320px",
                alignItems: "center",
                gap: 18,
                padding: "22px 26px",
                background: colors.white,
                border: `2px solid ${colors.line}`,
                borderRadius: 16,
                opacity: interpolate(frame, [80 + index * 24, 110 + index * 24], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
              }}
            >
              <strong style={{fontSize: 32, color: colors.blue}}>{sequence}</strong>
              <span style={{fontSize: 30, fontWeight: 700}}>{asset}</span>
              <code style={{fontSize: 23, color: colors.muted}}>{action}</code>
            </div>
          ))}
        </div>
        <div style={{display: "flex", flexDirection: "column", gap: 22}}>
          <div style={{background: colors.ink, color: colors.white, borderRadius: 24, padding: "44px"}}>
            <div style={{fontSize: 108, fontWeight: 900, color: "#7D9FD2"}}>17 / 17</div>
            <div style={{fontSize: 30, lineHeight: 1.35}}>unique graph assets grounded</div>
          </div>
          <div style={{background: colors.white, border: `2px solid ${colors.line}`, borderRadius: 24, padding: "38px"}}>
            <div style={{fontSize: 72, fontWeight: 900, color: colors.success}}>3 / 3</div>
            <div style={{fontSize: 28, color: colors.muted}}>live runs accepted · no retries</div>
          </div>
          <Pill tone="risk">Cannot change verdict or write targets</Pill>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const WriteBack = () => {
  const frame = useCurrentFrame();
  const checks = [
    "Planner status: accepted",
    "Decision Document updated",
    "Document read-back verified",
    "Source relationship verified",
  ];
  return (
    <AbsoluteFill style={{...base, padding: "92px 110px", opacity: fade(frame, 660)}}>
      <Eyebrow>Explicit DataHub mutation</Eyebrow>
      <div style={{display: "grid", gridTemplateColumns: "0.9fr 1.1fr", gap: 90, flex: 1, alignItems: "center"}}>
        <div>
          <h2 style={{fontSize: 88, lineHeight: 0.98, letterSpacing: "-0.05em", margin: "0 0 36px"}}>
            The decision becomes durable graph context.
          </h2>
          <div style={{fontSize: 28, color: colors.muted, lineHeight: 1.5}}>
            Existing Document updated idempotently.<br />Source + 17 impacted assets related.
          </div>
        </div>
        <div style={{background: colors.white, border: `2px solid ${colors.line}`, borderRadius: 28, padding: "50px", boxShadow: "0 28px 80px rgba(17,21,29,0.1)"}}>
          <code style={{display: "block", color: colors.blue, fontSize: 23, marginBottom: 34, overflowWrap: "anywhere"}}>
            urn:li:document:shared-cadcf907-2b52-4bd9-be46-f3831ca8eeb3
          </code>
          <div style={{display: "flex", flexDirection: "column", gap: 20}}>
            {checks.map((label, index) => (
              <div
                key={label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 20,
                  fontSize: 34,
                  fontWeight: 750,
                  opacity: interpolate(frame, [60 + index * 35, 90 + index * 35], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  }),
                }}
              >
                <span style={{width: 42, height: 42, borderRadius: 21, background: "#EAF7EF", color: colors.success, display: "grid", placeItems: "center"}}>✓</span>
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const Evaluation = () => {
  const frame = useCurrentFrame();
  const metrics = [
    ["16 / 16", "fixed scenarios"],
    ["130 / 130", "exact checks"],
    ["92", "automated tests"],
    ["0", "unsupported claims"],
  ];
  return (
    <AbsoluteFill style={{...base, padding: "92px 110px", opacity: fade(frame, 630)}}>
      <Eyebrow>Reliability is part of the product</Eyebrow>
      <h2 style={{fontSize: 82, letterSpacing: "-0.05em", margin: "24px 0 70px"}}>Evidence before confidence.</h2>
      <div style={{display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 28}}>
        {metrics.map(([value, label], index) => (
          <div
            key={label}
            style={{
              minHeight: 330,
              background: index === 3 ? colors.ink : colors.white,
              color: index === 3 ? colors.white : colors.ink,
              border: `2px solid ${index === 3 ? colors.ink : colors.line}`,
              borderRadius: 26,
              padding: "40px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              opacity: interpolate(frame, [40 + index * 26, 75 + index * 26], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <strong style={{fontSize: 68, color: index === 3 ? "#7D9FD2" : colors.blue}}>{value}</strong>
            <span style={{fontSize: 30, color: index === 3 ? "#D9DEE7" : colors.muted}}>{label}</span>
          </div>
        ))}
      </div>
      <div style={{marginTop: 52, display: "flex", gap: 22}}>
        <Pill tone="success">CI passed</Pill>
        <Pill tone="success">Pages passed</Pill>
        <Pill>Secret-isolated</Pill>
      </div>
    </AbsoluteFill>
  );
};

const Close = () => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 35], [0, 1], {extrapolateRight: "clamp"});
  return (
    <AbsoluteFill style={{...base, alignItems: "center", justifyContent: "center", opacity}}>
      <div style={{textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", gap: 32}}>
        <Eyebrow>LineageGuard</Eyebrow>
        <h2 style={{fontSize: 100, lineHeight: 0.98, letterSpacing: "-0.055em", margin: 0}}>
          Stop unsafe changes<br />before they ship.
        </h2>
        <div style={{fontSize: 34, color: colors.muted}}>Context → decision → validated action → durable knowledge</div>
        <Pill tone="success">Built with DataHub MCP</Pill>
      </div>
    </AbsoluteFill>
  );
};

export const LineageGuardRoughCut = () => {
  return (
    <AbsoluteFill style={base}>
      <Sequence from={150} durationInFrames={4782}>
        <Audio src={staticFile("audio/narration-rough.wav")} />
      </Sequence>
      <Sequence from={0} durationInFrames={720}>
        <Intro />
      </Sequence>
      <Sequence from={720} durationInFrames={1440}>
        <LiveReview />
      </Sequence>
      <Sequence from={2160} durationInFrames={1080}>
        <Planner />
      </Sequence>
      <Sequence from={3240} durationInFrames={660}>
        <WriteBack />
      </Sequence>
      <Sequence from={3900} durationInFrames={630}>
        <Evaluation />
      </Sequence>
      <Sequence from={4530} durationInFrames={570}>
        <Close />
      </Sequence>
    </AbsoluteFill>
  );
};
