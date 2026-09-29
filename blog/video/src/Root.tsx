import { Composition } from 'remotion';
import { Explainer } from './Explainer';
import { defaultProps, FPS, HEIGHT, WIDTH, type ExplainerProps } from './props';
import { Stat, Steps, STEPS_FPS, statDuration, stepsDuration, type StatProps, type StepsProps } from './Visuals';

export const Root = () => (
  <>
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
    <Composition
      id="Steps"
      component={Steps}
      width={1200}
      height={675}
      fps={STEPS_FPS}
      durationInFrames={STEPS_FPS * 6}
      defaultProps={{ lang: 'he', title: 'איך מתחילים', steps: ['רשימת משימות מפורשת', 'קובץ progress בין sessions', 'evaluator נפרד', 'כללים דטרמיניסטיים'] } as StepsProps}
      calculateMetadata={({ props }: { props: StepsProps }) => ({ durationInFrames: Math.round(stepsDuration(props)) })}
    />
    <Composition
      id="Stat"
      component={Stat}
      width={1200}
      height={675}
      fps={STEPS_FPS}
      durationInFrames={statDuration()}
      defaultProps={{ lang: 'he', value: '88%', label: 'הצלחה עם ה-harness הטוב, לעומת 68% עם הגרוע', source: 'Marmelab, 2026' } as StatProps}
    />
  </>
);
