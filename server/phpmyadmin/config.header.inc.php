<?php
echo '<link rel="stylesheet" href="./pi2000.css">';
/* Debian's newer Twig emits developer deprecations as user notices.
   Keep actionable warnings/errors; do not put dependency notices in row forms. */
if (isset($GLOBALS['errorHandler'])) {
    foreach ($GLOBALS['errorHandler']->getErrors() as $notice) {
        if (in_array($notice->getNumber(), [E_DEPRECATED, E_USER_DEPRECATED], true)) {
            $notice->isDisplayed(true);
        }
    }
}
$previous = null;
$previous = set_error_handler(static function ($number, $text, $file, $line) use (&$previous) {
    if ($number === E_DEPRECATED || $number === E_USER_DEPRECATED) { return true; }
    if ($previous) { return $previous($number, $text, $file, $line); }
    return false;
});
