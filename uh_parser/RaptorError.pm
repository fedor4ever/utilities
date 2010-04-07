# Copyright (c) 2009 Symbian Foundation Ltd
# This component and the accompanying materials are made available
# under the terms of the License "Eclipse Public License v1.0"
# which accompanies this distribution, and is available
# at the URL "http://www.eclipse.org/legal/epl-v10.html".
#
# Initial Contributors:
# Symbian Foundation Ltd - initial contribution.
#
# Contributors:
#
# Description:
# Raptor parser module.
# Extract, analyzes and dumps raptor errors i.e. content of <error> tags from a raptor log file

package RaptorError;

use strict;
use RaptorCommon;

our $reset_status = {};
my $buildlog_status = {};
my $buildlog_error_status = {};

$reset_status->{name} = 'reset_status';
$reset_status->{next_status} = {buildlog=>$buildlog_status};

$buildlog_status->{name} = 'buildlog_status';
$buildlog_status->{next_status} = {error=>$buildlog_error_status};
$buildlog_status->{on_start} = 'RaptorError::on_start_buildlog';

$buildlog_error_status->{name} = 'buildlog_error_status';
$buildlog_error_status->{next_status} = {};
$buildlog_error_status->{on_start} = 'RaptorError::on_start_buildlog_error';
$buildlog_error_status->{on_end} = 'RaptorError::on_end_buildlog_error';
$buildlog_error_status->{on_chars} = 'RaptorError::on_chars_buildlog_error';

my $filename = '';

my $raptor_error_info = {};

my $characters = '';

my $CATEGORY_RAPTORERROR = 'raptor_error';
my $CATEGORY_RAPTORERROR_CANNOTPROCESSSCHEMAVERSION = 'cannot_process_schema_version';
my $CATEGORY_RAPTORERROR_NOBLDINFFOUND = 'no_bld_inf_found';
my $CATEGORY_RAPTORERROR_CANTFINDMMPFILE = 'cant_find_mmp_file';
my $CATEGORY_RAPTORERROR_MAKEEXITEDWITHERRORS = 'make_exited_with_errors';
my $CATEGORY_RAPTORERROR_TOOLDIDNOTRETURNVERSION = 'tool_didnot_return_version';
my $CATEGORY_RAPTORERROR_UNKNOWNBUILDCONFIG = 'unknown_build_config';
my $CATEGORY_RAPTORERROR_NOBUILDCONFIGSGIVEN = 'no_build_configs_given';
my $CATEGORY_RAPTORERROR_COULDNOTEXPORT = 'missing_source_file';
my $CATEGORY_RAPTORERROR_MISSINGBLDINFFILE = 'missing_bld_inf_file';

sub process
{
	my ($text, $logfile, $component, $mmp, $phase, $recipe, $file) = @_;
	
	my $dumped = 1;
	
	my $category = $CATEGORY_RAPTORERROR;
	my $severity = '';
	my $subcategory = '';
	
	if ($text =~ m,Cannot process schema version .* of file,)
	{
		$severity = $RaptorCommon::SEVERITY_CRITICAL;
		$subcategory = $CATEGORY_RAPTORERROR_CANNOTPROCESSSCHEMAVERSION;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,No bld\.inf found at,)
	{
		$severity = $RaptorCommon::SEVERITY_MAJOR;
		$subcategory = $CATEGORY_RAPTORERROR_NOBLDINFFOUND;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,Can't find mmp file,)
	{
		$severity = $RaptorCommon::SEVERITY_MAJOR;
		$subcategory = $CATEGORY_RAPTORERROR_CANTFINDMMPFILE;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,The make-engine exited with errors,)
	{
		$severity = $RaptorCommon::SEVERITY_CRITICAL;
		$subcategory = $CATEGORY_RAPTORERROR_MAKEEXITEDWITHERRORS;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,tool .* from config .* did not return version .* as required,)
	{
		$severity = $RaptorCommon::SEVERITY_CRITICAL;
		$subcategory = $CATEGORY_RAPTORERROR_TOOLDIDNOTRETURNVERSION;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,Unknown build configuration '.*',)
	{
		$severity = $RaptorCommon::SEVERITY_CRITICAL;
		$subcategory = $CATEGORY_RAPTORERROR_UNKNOWNBUILDCONFIG;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,No build configurations given,)
	{
		$severity = $RaptorCommon::SEVERITY_CRITICAL;
		$subcategory = $CATEGORY_RAPTORERROR_NOBUILDCONFIGSGIVEN;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,Could not export .* to .* : \[Errno 2\] No such file or directory: .*,)
	{
		$severity = $RaptorCommon::SEVERITY_MAJOR;
		$subcategory = $CATEGORY_RAPTORERROR_COULDNOTEXPORT;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,win32/mingw/bin/cpp\.exe: .*bld\.inf:.*bld\.inf: No such file or directory,)
	{
		$severity = $RaptorCommon::SEVERITY_MAJOR;
		$subcategory = $CATEGORY_RAPTORERROR_MISSINGBLDINFFILE;
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	elsif ($text =~ m,^Preprocessor exception: ''Errors in .*bld\.inf'' : in command,)
	{
		# don't dump
		$dumped = 0;
	}
	elsif ($text =~ m,Source of export does not exist: .*,)
	{
		# don't dump
		$dumped = 0;
	}
	else # log everything by default
	{
		RaptorCommon::dump_fault($category, $subcategory, $severity, $logfile, $component, $mmp, $phase, $recipe, $file);
	}
	
	return $dumped;
}

sub on_start_buildlog
{
	RaptorCommon::init();
}

sub on_start_buildlog_error
{
  my ($el) = @_;
	
	#print "on_start_buildlog_error\n";
	
	$raptor_error_info = {};
	
	my $attributes = $el->{Attributes};
	for (keys %{$attributes})
	{
		$raptor_error_info->{$attributes->{$_}->{'LocalName'}} = $attributes->{$_}->{'Value'};
		#print "$_ -> $attributes->{$_}->{'Value'}\n";
	}
}

sub on_chars_buildlog_error
{
	my ($ch) = @_;
	
	#print "on_chars_buildlog_error\n";
	
	$characters .= $ch->{Data};
	
	#print "characters is now -->$characters<--\n";
}

sub on_end_buildlog_error
{
	#print "on_end_buildlog_error\n";
	
	my $package = '';
	if ($raptor_error_info->{bldinf})
	{
    $::allbldinfs->{$raptor_error_info->{bldinf}} = 1;
    
    # normalize bldinf path
		$raptor_error_info->{bldinf} = lc($raptor_error_info->{bldinf});
		$raptor_error_info->{bldinf} =~ s,^[A-Za-z]:,,;
		$raptor_error_info->{bldinf} =~ s,[\\],/,g;
		
		if ($raptor_error_info->{bldinf} =~ m,/((os|mw|app|tools|ostools|adaptation)/[^/]*),)
		{
			$package = $1;
			$package =~ s,/,_,;
		}
		else
		{
			print "WARNING: can't understand bldinf attribute of raptor error: $raptor_error_info->{bldinf}. Won't associate to package.\n";
		}
  }
	
	$characters =~ s,^[\r\n]*,,;
	$characters =~ s,[\r\n]*$,,;
	
	if ($characters =~ m,[^\s^\r^\n],)
	{
    my $bldinf_field = '';
    if ($package)
		{
			$filename = "$::raptorbitsdir/$package.txt";
			$bldinf_field = $raptor_error_info->{bldinf};
		}
		else
		{
		  $filename = "$::raptorbitsdir/raptor_error.txt";
		}
		
		if (!-f$filename)
		{
			print "Writing file $filename\n";
			open(FILE, ">$filename");
			close(FILE);
		}
		
		my $dumped = process($characters, $::current_log_file, $bldinf_field, '', '', '', "$package.txt");
		
		if ($dumped)
		{
			open(FILE, ">>$filename");
			print FILE "---failure_item_$::failure_item_number\---\n";
			print FILE "$characters\n\n";
			close(FILE);
		}
	}
	
	$characters = '';
}


1;