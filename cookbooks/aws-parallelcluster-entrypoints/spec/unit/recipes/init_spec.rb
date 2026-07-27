# frozen_string_literal: true

# Copyright:: 2026 Amazon.com, Inc. and its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the
# License. A copy of the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "LICENSE.txt" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and
# limitations under the License.

require 'spec_helper'
require 'ostruct'

describe 'aws-parallelcluster-entrypoints::init' do
  all_recipes = %w(
    aws-parallelcluster-platform::enable_chef_error_handler
    aws-parallelcluster-shared::setup_envars
    aws-parallelcluster-shared::remount_tmp_noexec
    aws-parallelcluster-environment::init
    aws-parallelcluster-computefleet::init
    aws-parallelcluster-slurm::init
  )

  remount_tmp_noexec_recipe = 'aws-parallelcluster-shared::remount_tmp_noexec'

  before do
    allow_any_instance_of(Chef::Recipe).to receive(:systemd?).and_return(true)
    allow_any_instance_of(Object).to receive(:fetch_config).and_return(OpenStruct.new)

    @included_recipes = []
    all_recipes.each do |recipe_name|
      allow_any_instance_of(Chef::Recipe).to receive(:include_recipe).with(recipe_name) do
        @included_recipes << recipe_name
      end
    end
  end

  for_all_oses do |platform, version|
    context "on #{platform}#{version}" do
      cached(:chef_run) do
        runner(platform: platform, version: version).converge(described_recipe)
      end

      it "includes the remount_tmp_noexec recipe right after setup_envars" do
        chef_run
        expect(@included_recipes).to include(remount_tmp_noexec_recipe)
        expect(@included_recipes.index(remount_tmp_noexec_recipe))
          .to eq(@included_recipes.index('aws-parallelcluster-shared::setup_envars') + 1)
      end
    end
  end
end
