import { Composition } from 'remotion';
import { Explainer } from './Explainer';
import { defaultProps, FPS, HEIGHT, WIDTH, type ExplainerProps } from './props';

export const Root = () => (
  <Composition
    id="Explainer"
    component={Explainer}
    width={WIDTH}
    height={HEIGHT}
    fps={FPS}
    durationInFrames={FPS * 30}
    defaultProps={defaultProps}
    calculateMetadata={({ props }: { props: ExplainerProps }) => ({
      durationInFrames: Math.max(FPS, Math.round(props.scenes.reduce((s, sc) => s + sc.durationSec, 0) * FPS)),
    })}
  />
);
