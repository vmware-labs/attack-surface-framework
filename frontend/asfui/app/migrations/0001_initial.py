# Generated by Django 4.2.4 on 2023-08-29 20:33

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='vdInServices',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('nname', models.CharField(default='unknown', max_length=150)),
                ('type', models.CharField(default='DOMAIN', max_length=30)),
                ('source', models.CharField(default='', max_length=60)),
                ('ipv4', models.CharField(default='', max_length=20)),
                ('ipv6', models.CharField(default='', max_length=150)),
                ('lastdate', models.DateTimeField(auto_now=True)),
                ('itemcount', models.IntegerField(default=0)),
                ('tag', models.CharField(default='', max_length=250)),
                ('ports', models.CharField(default='', max_length=250)),
                ('full_ports', models.TextField(default='')),
                ('service_ssh', models.CharField(default='', max_length=250)),
                ('service_rdp', models.CharField(default='', max_length=250)),
                ('service_telnet', models.CharField(default='', max_length=250)),
                ('service_ftp', models.CharField(default='', max_length=250)),
                ('service_smb', models.CharField(default='', max_length=250)),
                ('nuclei_http', models.TextField(default='')),
                ('info', models.TextField(default='')),
                ('info_gnmap', models.TextField(default='')),
                ('nse_vsanrce', models.CharField(default='', max_length=250)),
                ('owner', models.CharField(default='', max_length=512)),
                ('metadata', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdInTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('author', models.CharField(default='Me', max_length=100)),
                ('lastdate', models.DateTimeField(auto_now=True)),
                ('itemcount', models.IntegerField(default=0)),
                ('type', models.CharField(default='DOMAIN', max_length=100)),
                ('tag', models.CharField(default='DEFAULT', max_length=250)),
                ('owner', models.CharField(default='', max_length=512)),
                ('metadata', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdJob',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('input', models.CharField(default='amass', max_length=64)),
                ('regexp', models.CharField(default='', max_length=250)),
                ('exclude', models.CharField(default='', max_length=250)),
                ('module', models.CharField(default='error', max_length=250)),
                ('tag', models.CharField(default='', max_length=250)),
                ('info', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdRegExp',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('regexp', models.CharField(default='.*', max_length=250)),
                ('exclude', models.CharField(default='', max_length=250)),
                ('tag', models.CharField(default='', max_length=250)),
                ('info', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('type', models.CharField(default='DOMAIN', max_length=30)),
                ('source', models.CharField(default='', max_length=60)),
                ('ipv4', models.CharField(default='', max_length=20)),
                ('ipv6', models.CharField(default='', max_length=150)),
                ('lastdate', models.DateTimeField(auto_now=True)),
                ('itemcount', models.IntegerField(default=0)),
                ('tag', models.CharField(default='DEFAULT', max_length=250)),
                ('info', models.CharField(default='', max_length=250)),
                ('owner', models.CharField(default='', max_length=512)),
                ('metadata', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdServices',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('nname', models.CharField(default='unknown', max_length=150)),
                ('type', models.CharField(default='DOMAIN', max_length=30)),
                ('source', models.CharField(default='', max_length=60)),
                ('ipv4', models.CharField(default='', max_length=20)),
                ('ipv6', models.CharField(default='', max_length=150)),
                ('lastdate', models.DateTimeField(auto_now=True)),
                ('itemcount', models.IntegerField(default=0)),
                ('tag', models.CharField(default='', max_length=250)),
                ('ports', models.CharField(default='', max_length=250)),
                ('full_ports', models.TextField(default='')),
                ('service_ssh', models.CharField(default='', max_length=250)),
                ('service_rdp', models.CharField(default='', max_length=250)),
                ('service_telnet', models.CharField(default='', max_length=250)),
                ('service_ftp', models.CharField(default='', max_length=250)),
                ('service_smb', models.CharField(default='', max_length=250)),
                ('nuclei_http', models.TextField(default='')),
                ('info', models.TextField(default='')),
                ('info_gnmap', models.TextField(default='')),
                ('nse_vsanrce', models.CharField(default='', max_length=250)),
                ('owner', models.CharField(default='', max_length=512)),
                ('metadata', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdTarget',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True)),
                ('author', models.CharField(default='Me', max_length=100)),
                ('lastdate', models.DateTimeField(auto_now=True)),
                ('itemcount', models.IntegerField(default=0)),
                ('type', models.CharField(default='DOMAIN', max_length=100)),
                ('tag', models.CharField(default='DEFAULT', max_length=250)),
                ('owner', models.CharField(default='', max_length=512)),
                ('metadata', models.TextField(default='')),
            ],
        ),
        migrations.CreateModel(
            name='vdNucleiResult',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('tfp', models.IntegerField(default=-1)),
                ('type', models.CharField(default='DOMAIN', max_length=30)),
                ('source', models.CharField(default='', max_length=60)),
                ('ipv4', models.CharField(default='', max_length=20)),
                ('ipv6', models.CharField(default='', max_length=150)),
                ('lastdate', models.DateTimeField(auto_now=True)),
                ('firstdate', models.DateTimeField(blank=True)),
                ('bumpdate', models.DateTimeField(blank=True)),
                ('port', models.IntegerField(default=0)),
                ('protocol', models.CharField(default='tcp', max_length=40)),
                ('detectiondate', models.DateTimeField(blank=True)),
                ('vulnerability', models.CharField(max_length=128)),
                ('ptime', models.CharField(default='P1E', max_length=4)),
                ('scope', models.CharField(default='E', max_length=1)),
                ('engine', models.CharField(default='network', max_length=50)),
                ('level', models.CharField(default='critical', max_length=20)),
                ('uri', models.CharField(max_length=250)),
                ('full_uri', models.TextField()),
                ('uriistruncated', models.IntegerField(default=0)),
                ('nname', models.CharField(default='unknown', max_length=150)),
                ('itemcount', models.IntegerField(default=0)),
                ('tag', models.CharField(default='DEFAULT', max_length=250)),
                ('info', models.TextField(default='')),
                ('owner', models.CharField(default='', max_length=512)),
                ('metadata', models.TextField(default='')),
            ],
            options={
                'unique_together': {('vulnerability', 'name')},
            },
        ),
    ]
