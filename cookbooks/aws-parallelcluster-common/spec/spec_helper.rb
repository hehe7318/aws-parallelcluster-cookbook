require 'chefspec'
require 'chefspec/berkshelf'

module ChefSpec
  class Runner
    # Allows to converge a dynamic code block
    # For instance, it can be used to invoke actions on resources
    def converge_dsl(*recipes, &block)
      cookbook_name = 'any'
      recipe_name = 'any'
      converge(*recipes) do
        recipe = Chef::Recipe.new(cookbook_name, recipe_name, @run_context)
        recipe.instance_eval(&block)
      end
    end
  end
end

def for_oses(os_list)
  os_list.each do |platform, version|
    yield(platform, version)
  end
end

def for_all_oses
  [
    %w(amazon 2),
    # The only Centos7 version supported by ChefSpec
    # See the complete list here: https://github.com/chefspec/fauxhai/blob/main/PLATFORMS.md
    %w(centos 7.8.2003),
    %w(ubuntu 18.04),
    %w(ubuntu 20.04),
    %w(redhat 8),
  ].each do |platform, version|
    yield(platform, version)
  end
end

def mock_exist_call_original
  # This is required before mocking existence of specific files
  allow(File).to receive(:exist?).and_call_original
end

def mock_file_exists(file, exists)
  allow(::File).to receive(:exist?).with(file).and_return(exists)
end