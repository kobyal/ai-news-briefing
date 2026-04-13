from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct


class TriggerStack(Stack):
    """Lambda + EventBridge rules that dispatch the GitHub Actions pipeline."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.fn = _lambda.Function(
            self,
            "TriggerFunction",
            function_name="ai-news-trigger",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/trigger"),
            timeout=Duration.seconds(30),
            memory_size=128,
            environment={
                "GITHUB_PAT": "REPLACE_ME",  # set manually or via SSM
            },
        )

        # 06:00 Israel time (03:00 UTC) — daily pipeline trigger
        daily = events.Rule(
            self,
            "TriggerDaily",
            rule_name="ai-news-trigger-daily",
            schedule=events.Schedule.cron(hour="3", minute="0"),
        )
        daily.add_target(targets.LambdaFunction(self.fn))
