packer {
  required_plugins {
    vmware = {
      source  = "github.com/hashicorp/vmware"
      version = "~> 1"
    }
  }
}

variable "vm_name" {
  type    = string
  default = "wifi-capture"
}

variable "iso_url" {
  type    = string
  default = "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/x86_64/alpine-virt-3.19.0-x86_64.iso"
}

variable "iso_checksum" {
  type    = string
  default = "sha256:366317d854d77fc5db3b2fd774f5e27b1f1a1b1c3d9e8e9a8c6b3c1b0e8e0e8e"
}

source "vmware-iso" "alpine" {
  vm_name          = var.vm_name
  guest_os_type    = "other5xlinux-64"
  
  iso_url          = var.iso_url
  iso_checksum     = "none"
  
  ssh_username     = "root"
  ssh_password     = "wifi-capture"
  ssh_timeout      = "30m"
  
  cpus             = 1
  memory           = 512
  disk_size        = 2048
  disk_type_id     = "0"
  
  headless         = false
  
  vmx_data = {
    "usb.present"           = "TRUE"
    "usb.generic.autoconnect" = "TRUE"
    "ehci.present"          = "TRUE"
  }
  
  network_adapter_type = "e1000"
  
  http_directory   = "http"
  
  boot_wait        = "30s"
  boot_command     = [
    "root<enter><wait5>",
    "setup-alpine -q<enter><wait5>",
    "us<enter><wait>",
    "us<enter><wait>",
    "${var.vm_name}<enter><wait>",
    "dhcp<enter><wait>",
    "<enter><wait>",
    "wifi-capture<enter><wait>",
    "wifi-capture<enter><wait>",
    "UTC<enter><wait>",
    "<enter><wait>",
    "1<enter><wait>",
    "openssh<enter><wait>",
    "<enter><wait>",
    "sda<enter><wait>",
    "sys<enter><wait>",
    "y<enter><wait60>",
    "reboot<enter><wait60>",
    "root<enter><wait5>",
    "wifi-capture<enter><wait5>",
    "echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config<enter>",
    "service sshd restart<enter><wait5>"
  ]
  
  shutdown_command = "poweroff"
  
  output_directory = "../output"
}

build {
  sources = ["source.vmware-iso.alpine"]
  
  provisioner "shell" {
    scripts = [
      "scripts/setup.sh",
      "scripts/network.sh",
      "scripts/autostart.sh"
    ]
  }
  
  provisioner "file" {
    source      = "../../web"
    destination = "/opt/wifi-capture/"
  }
  
  provisioner "file" {
    source      = "../../data"
    destination = "/opt/wifi-capture/"
  }
  
  post-processor "shell-local" {
    inline = ["echo 'Build complete! OVA exported to output/'"]
  }
}
