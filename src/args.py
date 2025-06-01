def vpc_arguments(parser):
    parser.add_argument(
        "--cidr",
        required=True,
        help="CIDR block for the VPC (e.g. 10.0.0.0/16)"
    )

    parser.add_argument(
        "--name",
        required=False,
        help="Tag name for the VPC"
    )


def tag_vpc_arguments(parser):
    parser.add_argument(
        "--resource-id",
        required=True,
        help="The VPC ID to tag (e.g., vpc-xxxxxx)"
    )

    parser.add_argument(
        "--key",
        required=True,
        help="Tag key (e.g., Name)"
    )

    parser.add_argument(
        "--value",
        required=True,
        help="Tag value (e.g., my-vpc)"
    )


def igw_arguments(parser):
    parser.add_argument(
        "--create",
        action="store_true",
        help="Flag to create a new Internet Gateway"
    )

    parser.add_argument(
        "--attach",
        action="store_true",
        help="Flag to attach an existing IGW to a VPC"
    )

    parser.add_argument(
        "--igw-id",
        type=str,
        help="ID of the Internet Gateway to attach (required if using --attach)"
    )

    parser.add_argument(
        "--vpc-id",
        type=str,
        help="ID of the VPC to attach to (required if using --attach)"
    )


def subnet_arguments(parser):
    parser.add_argument("--vpc-id", required=True, help="VPC ID for the subnet")
    parser.add_argument("--cidr", required=True, help="CIDR block for the subnet")
    parser.add_argument("--public", action="store_true", help="Mark subnet as public")


def ec2_arguments(parser):
    parser.add_argument(
        "--vpc-id",
        required=True,
        help="Existing VPC ID (e.g. vpc-0abc1234def56789)"
    )
    parser.add_argument(
        "--subnet-id",
        required=True,
        help="Subnet to place the instance in"
    )
    parser.add_argument(
        "--ami-id",
        required=False,
        help="Custom AMI ID (defaults to latest Amazon Linux 2)"
    )
    parser.add_argument(
        "--key-name",
        default="auto-keypair",
        help="Key pair name (will be created if absent)"
    )
    parser.add_argument(
        "--sg-name",
        default="auto-sg",
        help="Security-group name (will be created if absent)"
    )
