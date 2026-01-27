# Slurm
default['cluster']['slurm']['version'] = '25-11-2-1'
default['cluster']['slurm']['commit'] = ''
default['cluster']['slurm']['branch'] = ''
default['cluster']['slurm']['sha256'] = '719783317e46b6241ab5c8f1e3f91e1e34fda63b5a1cd21403fa7696ec8d517c'
default['cluster']['slurm']['base_url'] = "#{node['cluster']['artifacts_s3_url']}/dependencies/slurm"
# Munge
default['cluster']['munge']['munge_version'] = '0.5.16'
default['cluster']['munge']['sha256'] = 'fa27205d6d29ce015b0d967df8f3421067d7058878e75d0d5ec3d91f4d32bb57'
default['cluster']['munge']['base_url'] = "#{node['cluster']['artifacts_s3_url']}/dependencies/munge"
# LibJwt
default['cluster']['jwt']['version'] = '2.1.2'
default['cluster']['jwt']['sha256'] = 'cb6114ea6a01a61367fdb7fc11ee708110e3c7f7fc74a6c3266c03321841ee17'
if platform?('amazon') && node['platform_version'] == "2"
  default['cluster']['jwt']['version'] = '1.17.0'
  default['cluster']['jwt']['sha256'] = '617778f9687682220abf9b7daacbe72bab7c2985479f8bee4db9648bd2440687'
end
default['cluster']['jwt']['base_url'] = "#{node['cluster']['artifacts_s3_url']}/dependencies/jwt"
