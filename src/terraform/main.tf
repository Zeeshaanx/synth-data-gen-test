provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "ubuntu_instance" {
  ami                    = "ami-0fc5d935ebf8bc3bc"  # Ubuntu 22.04 LTS (us-east-1)
  instance_type          = "r5.large"
  key_name               = "wldsh-dev"
  vpc_security_group_ids = [data.aws_security_group.launch_wizard.id]

  root_block_device {
    volume_size = 100
    volume_type = "gp2"
  }

  tags = {
    Name = "NemoDataDesigner"
  }
}

data "aws_security_group" "launch_wizard" {
  filter {
    name   = "group-name"
    values = ["launch-wizard-2"]
  }
}

output "instance_public_ip" {
  value = aws_instance.ubuntu_instance.public_ip
}

resource "local_file" "ansible_inventory" {
  content = <<EOF
[all]
${aws_instance.ubuntu_instance.public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=key-path

[all:vars]
ansible_python_interpreter=/usr/bin/python3
EOF

  filename = "${path.module}/../ansible/inventory"
}
