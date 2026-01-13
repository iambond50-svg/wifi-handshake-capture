# -*- mode: ruby -*-
# vi: set ft=ruby :
# WiFi Handshake Capture - 超轻量级虚拟机配置
# 使用 Alpine Linux，内存仅需 512MB

Vagrant.configure("2") do |config|
  config.vm.box = "generic/alpine318"
  config.vm.hostname = "wifi-capture"
  
  # 轻量级配置
  config.vm.provider "virtualbox" do |vb|
    vb.memory = "512"
    vb.cpus = 1
    vb.name = "wifi-handshake-capture"
    
    # USB 直通配置（需要 VirtualBox Extension Pack）
    vb.customize ["modifyvm", :id, "--usb", "on"]
    vb.customize ["modifyvm", :id, "--usbehci", "on"]
    
    # 自动添加 USB 无线网卡过滤器（常见芯片组）
    # Ralink/MediaTek
    vb.customize ["usbfilter", "add", "0", "--target", :id, "--name", "Ralink", "--vendorid", "148f"]
    # Realtek
    vb.customize ["usbfilter", "add", "1", "--target", :id, "--name", "Realtek", "--vendorid", "0bda"]
    # Atheros
    vb.customize ["usbfilter", "add", "2", "--target", :id, "--name", "Atheros", "--vendorid", "0cf3"]
    # Alfa Networks
    vb.customize ["usbfilter", "add", "3", "--target", :id, "--name", "Alfa", "--vendorid", "0e8d"]
  end
  
  # 共享文件夹：捕获的握手包会同步到 Windows
  config.vm.synced_folder "./captures", "/home/vagrant/captures", create: true
  config.vm.synced_folder "./scripts", "/home/vagrant/scripts", create: true
  config.vm.synced_folder "./config", "/home/vagrant/config", create: true
  
  # 自动配置环境
  config.vm.provision "shell", path: "scripts/setup.sh"
end
