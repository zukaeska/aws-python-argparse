from botocore.exceptions import ClientError, NoCredentialsError
import ipaddress


def validate_cidr(cidr_block):
    try:
        ipaddress.IPv4Network(cidr_block)
        return True
    except ValueError:
        print(f"Invalid CIDR block: {cidr_block}")
        return False


def create_vpc(ec2_client, cidr_block):
    try:
        if not validate_cidr(cidr_block):
            return
        response = ec2_client.create_vpc(CidrBlock=cidr_block)
        vpc_id = response['Vpc']['VpcId']
        print(f"VPC created: {vpc_id}")
        return vpc_id
    except ClientError as e:
        print(f"Failed to create VPC: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def tag_vpc(ec2_client, vpc_id, key, value):
    try:
        ec2_client.create_tags(
            Resources=[vpc_id],
            Tags=[{'Key': key, 'Value': value}]
        )
        print(f"Tag '{key}={value}' added to resource: {vpc_id}")
    except ClientError as e:
        print(f"Failed to tag resource: {e}")
    except Exception as e:
        print(f"Unexpected error while tagging: {e}")


def create_igw(ec2_client):
    try:
        response = ec2_client.create_internet_gateway()
        igw_id = response['InternetGateway']['InternetGatewayId']
        print(f"Internet Gateway created: {igw_id}")
        return igw_id
    except ClientError as e:
        print(f"Failed to create Internet Gateway: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def attach_igw(ec2_client, igw_id, vpc_id):
    try:
        ec2_client.attach_internet_gateway(
            InternetGatewayId=igw_id,
            VpcId=vpc_id
        )
        print(f"Internet Gateway {igw_id} attached to VPC {vpc_id}")
    except ClientError as e:
        print(f"Failed to attach Internet Gateway: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def create_subnet_with_route_table(ec2_client, vpc_id, cidr_block, is_public=False):
    try:
        if not validate_cidr(cidr_block):
            return
        # Create subnet
        subnet_resp = ec2_client.create_subnet(
            VpcId=vpc_id,
            CidrBlock=cidr_block
        )
        subnet_id = subnet_resp['Subnet']['SubnetId']
        print(f"Subnet created: {subnet_id}")

        # Create route table
        rt_resp = ec2_client.create_route_table(VpcId=vpc_id)
        rt_id = rt_resp['RouteTable']['RouteTableId']
        print(f"Route table created: {rt_id}")

        # Associate route table with subnet
        ec2_client.associate_route_table(RouteTableId=rt_id, SubnetId=subnet_id)
        print(f"Route table {rt_id} associated with subnet {subnet_id}")

        if is_public:
            # Get IGW ID from the VPC (find first attached one)
            igws = ec2_client.describe_internet_gateways(
                Filters=[{"Name": "attachment.vpc-id", "Values": [vpc_id]}]
            )["InternetGateways"]
            if not igws:
                print("No Internet Gateway attached to this VPC.")
                return

            igw_id = igws[0]['InternetGatewayId']
            ec2_client.create_route(
                RouteTableId=rt_id,
                DestinationCidrBlock="0.0.0.0/0",
                GatewayId=igw_id
            )
            print(f"Public route (0.0.0.0/0 → {igw_id}) added to route table {rt_id}")

    except ClientError as e:
        print(f"AWS ClientError: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")


def test_connection(aws_client):
    try:
        aws_client.list_buckets()
        print("AWS credentials are valid. Connection successful.")
    except NoCredentialsError:
        print("No AWS credentials found.")
    except ClientError as e:
        print(f"Failed to connect to AWS: {e}")

