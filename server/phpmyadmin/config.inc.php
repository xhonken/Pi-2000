<?php
/* Only the authenticated Pi-2000 gateway can supply FastCGI parameters. */
$bridge = json_decode(base64_decode($_SERVER['PI2000_BRIDGE'] ?? '', true) ?: '', true);
if (!is_array($bridge) || !preg_match('/^[a-f0-9]{48}$/', $bridge['sid'] ?? '')) {
    http_response_code(403); exit('Open MariaDB Manager from Pi-2000.');
}
$private = '/var/lib/pi2000-phpmyadmin/' . $bridge['sid'];
if (!is_dir($private)) { mkdir($private, 0700, true); }
$cfg['SessionSavePath'] = $private;
$cfg['TempDir'] = $private;
$cfg['PmaAbsoluteUri'] = $bridge['base'];
$cfg['AllowThirdPartyFraming'] = 'sameorigin';
$cfg['Servers'][1] = [
 'auth_type'=>'config', 'host'=>$bridge['host']==='localhost'?'127.0.0.1':$bridge['host'],
 'port'=>(string)$bridge['port'], 'user'=>$bridge['username'], 'password'=>$bridge['password'],
 'verbose'=>$bridge['name'], 'AllowNoPassword'=>true,
 'ssl'=>$bridge['tls']==='verify', 'ssl_verify'=>true, 'compress'=>false,
];
if ($bridge['tls']==='verify') {
    $ca=$bridge['ca'] ?: file_get_contents('/etc/ssl/certs/ca-certificates.crt');
    file_put_contents($private.'/ca.pem',$ca);
    $cfg['Servers'][1]['ssl_ca']=$private.'/ca.pem';
}
$cfg['ServerDefault']=1;
$cfg['Lang']='en';
$cfg['SendErrorReports']='never';
$cfg['VersionCheck']=false;
$cfg['UploadDir']='';
$cfg['SaveDir']='';
$cfg['ExecTimeLimit']=300;
$cfg['MemoryLimit']='256M';
$cfg['LoginCookieValidity']=1800;
$cfg['ShowPhpInfo']=false;
$cfg['ShowServerInfo']=true;
$cfg['AllowArbitraryServer']=false;
$cfg['NavigationTreeEnableGrouping']=false;
$cfg['UserprefsDisallow']=['SendErrorReports'];
