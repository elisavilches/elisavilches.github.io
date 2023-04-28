# coding: utf-8

Gem::Specification.new do |spec|
  spec.name          = "maldekstra-airspace-jekyll"
  spec.summary       = "A modified version of the Airspace theme for Jekyll."
  spec.version       = "0.1.0"
  spec.authors       = ["Alberto Lumbreras"]  
  spec.license       = "MIT"
   
  spec.files         = `git ls-files -z`.split("\x0").select { |f| f.match(%r{^(_layouts|_includes|_sass|LICENSE|README)/i}) }

  spec.required_ruby_version = ">= 2.4.0"
  spec.add_development_dependency "jekyll", "~> 4.2"
  spec.add_development_dependency "bundler", ">= 2.0"
  spec.add_development_dependency "rake", ">= 12.0"
end