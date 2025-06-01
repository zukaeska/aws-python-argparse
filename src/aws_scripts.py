from botocore.exceptions import ClientError, NoCredentialsError
import ipaddress
import os
import time
import socket
import urllib.request
import boto3


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


def _get_my_public_ip():
    try:
        with urllib.request.urlopen("https://checkip.amazonaws.com/", timeout=5) as r:
            return r.read().decode().strip()
    except Exception as e:
        print(f"Could not determine your public IP automatically: {e}")
        return None


def _get_latest_amazon_linux_ami(ec2_client) -> str:
    images = ec2_client.describe_images(
        Owners=["amazon"],
        Filters=[
            {"Name": "name", "Values": ["amzn2-ami-hvm-*-x86_64-gp2"]},
            {"Name": "state", "Values": ["available"]},
        ],
    )["Images"]
    if not images:
        raise RuntimeError("Could not find an Amazon Linux 2 AMI in this region.")
    return max(images, key=lambda im: im["CreationDate"])["ImageId"]


def _create_security_group(ec2_client, vpc_id: str, group_name: str, my_ip: str) -> str:
    try:
        sg_id = ec2_client.create_security_group(
            GroupName=group_name,
            Description="Auto SG for web+ssh",
            VpcId=vpc_id,
        )["GroupId"]
        print(f"Created security-group {sg_id}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "InvalidGroup.Duplicate":
            raise
        sg_id = ec2_client.describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [group_name]},
                {"Name": "vpc-id", "Values": [vpc_id]},
            ]
        )["SecurityGroups"][0]["GroupId"]
        print(f"Re-using existing security-group {sg_id}")

    ip_permissions = [
        {  # HTTP 0.0.0.0/0
            "IpProtocol": "tcp",
            "FromPort": 80,
            "ToPort": 80,
            "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
        }
    ]
    if my_ip:
        ip_permissions.append(
            {  # SSH from my public IP
                "IpProtocol": "tcp",
                "FromPort": 22,
                "ToPort": 22,
                "IpRanges": [{"CidrIp": f"{my_ip}/32"}],
            }
        )
    try:
        ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=ip_permissions)
        print("Ingress rules applied.")
    except ClientError as e:
        if "InvalidPermission.Duplicate" not in str(e):
            raise
    return sg_id


def _create_key_pair(ec2_client, key_name: str, save_dir: str = ".") -> None:
    key_path = os.path.join(save_dir, f"{key_name}.pem")
    try:
        key_material = ec2_client.create_key_pair(KeyName=key_name)["KeyMaterial"]
        with open(key_path, "w") as fp:
            fp.write(key_material)
        os.chmod(key_path, 0o400)
        print(f"Key pair saved to {key_path}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "InvalidKeyPair.Duplicate":
            raise
        print(f"Re-using existing key pair {key_name}")
        if not os.path.exists(key_path):
            print("⚠️  Key file not found locally – make sure you still have it!")


def _launch_instance(
    ec2_client,
    subnet_id: str,
    sg_id: str,
    key_name: str,
    ami_id: str,
    instance_type: str = "t2.micro",
) -> tuple[str, str]:
    resp = ec2_client.run_instances(
        ImageId=ami_id,
        InstanceType=instance_type,
        KeyName=key_name,
        MinCount=1,
        MaxCount=1,
        NetworkInterfaces=[
            {
                "DeviceIndex": 0,
                "SubnetId": subnet_id,
                "AssociatePublicIpAddress": True,
                "Groups": [sg_id],
            }
        ],
        BlockDeviceMappings=[
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {"VolumeSize": 10, "VolumeType": "gp2", "DeleteOnTermination": True},
            }
        ],
        TagSpecifications=[
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": "auto-ec2"}]}
        ],
    )
    instance_id = resp["Instances"][0]["InstanceId"]
    print(f"Started instance {instance_id}. Waiting until running …")

    ec2_res = boto3.resource("ec2", region_name=ec2_client.meta.region_name)
    inst = ec2_res.Instance(instance_id)
    inst.wait_until_running()
    inst.reload()
    print(f"Instance {instance_id} is running with public IP {inst.public_ip_address}")
    return instance_id, inst.public_ip_address


def _check_ssh(public_ip: str, timeout_sec: int = 120) -> None:
    print("Checking SSH connectivity …")
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            with socket.create_connection((public_ip, 22), timeout=5):
                print("✅ SSH port reachable!")
                return
        except OSError:
            time.sleep(5)
    print("⚠️  Could not reach SSH port within the timeout window.")


# ------------------------------------------------------------------
# Public entry called from main.py
# ------------------------------------------------------------------
def launch_ec2_workflow(
    ec2_client,
    vpc_id: str,
    subnet_id: str,
    key_name: str = "auto-keypair",
    sg_name: str = "auto-sg",
    ami_id: str | None = None,
):
    """
    Orchestrates the whole flow: SG → Key → Instance → Connectivity check.
    """
    my_ip = _get_my_public_ip()
    sg_id = _create_security_group(ec2_client, vpc_id, sg_name, my_ip)
    _create_key_pair(ec2_client, key_name)
    if ami_id is None:
        ami_id = _get_latest_amazon_linux_ami(ec2_client)
        print(f"Using AMI {ami_id}")
    _, public_ip = _launch_instance(ec2_client, subnet_id, sg_id, key_name, ami_id)
    _check_ssh(public_ip)


