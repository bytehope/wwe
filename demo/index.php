<?php
    ini_set('display_errors', '0');
    $doc = new \DOMDocument();
    $doc->loadXML($_POST['user_input']); // #1 

    $xml = $doc->saveXML();
    $doc = new \DOMDocument('1.0', 'UTF-8');
    $doc->loadXML($xml, LIBXML_DTDLOAD | LIBXML_NONET); // #2 & #3 

    foreach ($doc->childNodes as $child) {
        if ($child->nodeType === XML_DOCUMENT_TYPE_NODE) {// #4
            throw new RuntimeException('Dangerous XML detected');
        }
    }
