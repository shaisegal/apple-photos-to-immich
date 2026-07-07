class ApplePhotosToImmich < Formula
  include Language::Python::Virtualenv

  desc "Migrate Apple Photos libraries to Immich"
  homepage "https://github.com/shaisegal/apple-photos-to-immich"
  url "https://github.com/shaisegal/apple-photos-to-immich/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_REAL_SHA256"
  license "MIT"

  depends_on "python@3.12"

  resource "requests" do
    url "https://files.pythonhosted.org/packages/source/r/requests/requests-2.34.2.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/source/c/certifi/certifi-2026.6.17.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/source/c/charset-normalizer/charset_normalizer-3.4.8.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/source/i/idna/idna-3.18.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/source/u/urllib3/urllib3-2.7.0.tar.gz"
    sha256 "REPLACE_WITH_REAL_SHA256"
  end

  def install
    virtualenv_install_with_resources
    bin.install_symlink libexec/"bin/apple-photos-to-immich"
  end

  test do
    assert_match "apple-photos-to-immich", shell_output("#{bin}/apple-photos-to-immich --help")
  end
end
