from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_dynamodb as dynamodb,
)
from constructs import Construct


class IngestStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        table: dynamodb.Table,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.fn = _lambda.Function(
            self,
            "IngestFunction",
            function_name="ai-news-ingest",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.lambda_handler",
            code=_lambda.Code.from_asset("lambdas/ingest"),
            timeout=Duration.minutes(5),
            memory_size=256,
            environment={
                "TABLE_NAME": table.table_name,
                "GITHUB_PAGES_BASE": "https://kobyal.github.io/ai-news-briefing/data",
            },
        )

        table.grant_read_write_data(self.fn)

        # 06:20 Israel time (03:20 UTC) — after pipeline completes (~12 min)
        daily = events.Rule(
            self,
            "IngestDaily",
            rule_name="ai-news-ingest-daily",
            schedule=events.Schedule.cron(hour="3", minute="20"),
        )
        daily.add_target(targets.LambdaFunction(self.fn))
