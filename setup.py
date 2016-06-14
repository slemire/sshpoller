from distutils.core import setup

setup(
    name='sshpoller',
    version='0.1',
    packages=[''],
    url='https://github.com/slemire/sshpoller',
    license='',
    author='Simon Lemire',
    author_email='lemire.simon@gmail.com',
    description='SSH screen scrapper with InfluxDB output support', requires=['netmiko', 'influxdb', 'textfsm']
)
