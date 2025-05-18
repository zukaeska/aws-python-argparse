# src/main.py

import argparse
from auth import init_client
import aws_scripts as aws_scripts
from args import vpc_arguments, tag_vpc_arguments, igw_arguments, subnet_arguments


parser = argparse.ArgumentParser(
    description="AWS CLI Tool",
    prog='main.py',
    epilog='Tool to operate with AWS CLI'
)
subparsers = parser.add_subparsers(dest='command', required=True)

# Command: test-connection
subparsers.add_parser("test-connection", help="Verify AWS credentials and connectivity")

# Command: create-vpc
vpc_parser = subparsers.add_parser("create-vpc", help="Create a new VPC")
vpc_arguments(vpc_parser)

# Command: tag-vpc
tag_parser = subparsers.add_parser("tag-vpc", help="Add or update a tag on a VPC")
tag_vpc_arguments(tag_parser)

igw_parser = subparsers.add_parser("igw", help="Manage Internet Gateways")
igw_arguments(igw_parser)

subnet_parser = subparsers.add_parser("subnet", help="Create subnet and route table")
subnet_arguments(subnet_parser)


def main():
    aws_client = init_client("ec2")
    args = parser.parse_args()

    match args.command:
        case "test-connection":
            aws_scripts.test_connection(aws_client)

        case "create-vpc":
            vpc_id = aws_scripts.create_vpc(aws_client, args.cidr)
            if vpc_id and args.name:
                aws_scripts.tag_vpc(aws_client, vpc_id, "Name", args.name)

        case "tag-vpc":
            aws_scripts.tag_vpc(aws_client, args.resource_id, args.key, args.value)

        case "igw":
            if args.create:
                aws_scripts.create_igw(aws_client)
            elif args.attach and args.igw_id and args.vpc_id:
                aws_scripts.attach_igw(aws_client, args.igw_id, args.vpc_id)
            else:
                print("Invalid IGW command. Use --create or --attach with --igw-id and --vpc-id.")

        case "subnet":
            aws_scripts.create_subnet_with_route_table(
                aws_client,
                args.vpc_id,
                args.cidr,
                is_public=args.public
            )


if __name__ == "__main__":
    main()
