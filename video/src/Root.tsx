import {Composition} from "remotion";
import {LineageGuardRoughCut} from "./LineageGuardRoughCut";

export const RemotionRoot = () => {
  return (
    <Composition
      id="LineageGuardRoughCut"
      component={LineageGuardRoughCut}
      durationInFrames={5100}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{}}
    />
  );
};
