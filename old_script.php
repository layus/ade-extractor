<?php
ini_set ('max_execution_time', 0);
//----------------------------------------------------------------------
//                             FONCTION
//----------------------------------------------------------------------
function CutDate($date) {
	$ar = explode("/",$date);
	return $ar[2].$ar[0].$ar[1];
}

function CatHeure($heure) {
	$heures = explode('h',$heure); //0=h,1=min
	return $heures;
}

function HFin($debut,$duree) {
	$duree = str_replace('min','',$duree);
	$duree_ar = explode('h',$duree);
	$dureeh = $duree_ar[0]; // comme il y a des cours de la forme 15min, on pourrait donc avoir des minutes dans duree_ar[0]
	$dureem = (isset($duree_ar[1]))?$duree_ar[1]:$duree_ar[0]; // si on a une duree de la forme 2h , dureem est vide (0 pour une addition)

	$finm = $debut[1]+$dureem;
		if(($finm)>=60) {
		$debut[0]=$debut[0]+1;
		$finm = $finm-60;
		}
	$finm = (strlen($finm)<2)?'0'.$finm:$finm;// on rajoute le 0 si l'heure de fin est 8h09 par exemple
	$finh = $debut[0]+$dureeh; // on suppose qu'on aura jamais cours après minuit, et qu'on inclu pas les s*n* dans l'edt ADE...
	$finh = (strlen($finh)<2)?'0'.$finh:$finh; // la meme que pour les minutes
	$final = $finh.$finm.'00'; // la forme ics est hhmmss, donc on met ss Ã  00
	return $final;
}

function getFile($mode,$buffer){
    //Purge des anciens fichiers
		$dir = opendir($mode);
		while(($file=readdir($dir))==true){
		$file=$mode.'/'.$file;
		
		if ((time()-fileatime($file) > 60*60) and !(is_dir($file))){ // verification de la date, supression au bout d'une heure
			unlink($file);
			}
		}
    // Sortie du fichier
		$nameFile= $mode.'/ade'.time().'.'.$mode; // Création du nom de fichier cause variation de timestamp
		$file = fopen($nameFile,'w+');
		fputs($file,$buffer);
		fclose($file);
		chmod($nameFile, 0504);
		return($nameFile);
}
function getNameFromURLCODE($urlgeneral,$urleve,$idcookie){
$ch2 = curl_init();
curl_setopt($ch2, CURLOPT_HEADER, 0);
curl_setopt($ch2, CURLOPT_COOKIEFILE, realpath("cookie_".$idcookie.".txt"));
curl_setopt($ch2, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch2, CURLOPT_USERAGENT, 'Mozilla 5/0'); // utf-8
curl_setopt($ch2, CURLOPT_URL, $urlgeneral.$urleve);
$infoprecise = curl_exec($ch2);

	curl_close($ch2);
			$infoprecise = str_replace('<BODY>','',$infoprecise);
			$infoprecise = str_replace('&amp;','&',$infoprecise);
			$infoprecise = str_replace('&','&amp;',$infoprecise);
	        $infoprecise = str_replace('Code: ','',$infoprecise); //suppression de la mise en page de la page
	
    $dom = new DOMDocument(); // creation d'un objet DOM pour lire le html	
	
    $dom->loadHTML($infoprecise) or die('erreur');
    $bientotretour = $dom->getElementsByTagName('label');
	
// retour valeur + minuscule avec majuscule à chaque mot
	// L'item 0 : "intitulé du cours";
	// L'item 1 : Type : "MAGISTRAL OU TP";
	// L'item 2 : Web : "site web (generalement pas complet)";
	// L'item 3 : Notes : "Notes sur le cours";

// ici on ne renvois que l'item 0 les autres étant inutile dans le script 
// le Type pourrait être utile savoir si tp ou cours :) mais j'ai la flemme 
// de le récuperer et de concatener les deux
return(ucwords(strtolower($bientotretour->item(0)->nodeValue))); 
}




//----------------------------------------------------------------------
//                             PAGE HTML
//----------------------------------------------------------------------
   $url = 'http://horaire.sgsi.ucl.ac.be:8080';
 
	// Choix du projet :
		//creation cookie de connection
			$id= rand(0,10000);
			$fhs = fopen("cookie_co_".$id.".txt","w");
			fclose($fhs);
			// On remplis le cookies
					$ch = curl_init();
					curl_setopt($ch, CURLOPT_HEADER, 0);
					curl_setopt($ch, CURLOPT_COOKIEJAR, realpath("cookie_co_".$id.".txt"));
					curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
					curl_setopt($ch, CURLOPT_USERAGENT, 'Mozilla 5/0'); // utf-8
					curl_setopt($ch, CURLOPT_URL, $url.'/ade/custom/modules/plannings/direct_planning.jsp?weeks=40&login=etudiant&password=student');
						curl_exec($ch);
					curl_close($ch);
		// utilisation du cookies pour se connecter à la page du choix des projet.
		            $ch = curl_init();
					curl_setopt($ch, CURLOPT_HEADER, 0);
					curl_setopt($ch, CURLOPT_COOKIEFILE, realpath("cookie_co_".$id.".txt"));
					curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
					curl_setopt($ch, CURLOPT_USERAGENT, 'Mozilla 5/0'); // utf-8
					curl_setopt($ch, CURLOPT_URL, $url.'/ade/standard/projects.jsp');
						$sourceprojet = curl_exec($ch);
					curl_close($ch);
					
		//On supprime le code html inutile.
		      $sourceprojet = preg_replace('#\<HTML(.+)\<SELECT#isU', '', $sourceprojet);
              $sourceprojet = preg_replace('#\</SELECT\>(.+)\</HTML\>#isU', '', $sourceprojet);
    unlink(realpath("cookie_co_".$id.".txt"));
		
?>

<form class="top" id="formulaire" method="post" action="ade.php">
	<p>
	   Le projet souhaité :
	    <select <?php echo($sourceprojet); ?> </select><br/>
		<?php
		$semaines='';
		for ($i = 0; $i+date("W")+14 <= 40; $i++)
		{
			$suivant=$i+date("W")+14;
			$semaines .= ','.$suivant;
		}
		$semaines = ltrim($semaines,','); //supprime la premiere virgule
		?>
		<label for="codes">Codes cours (séparés par virgules) :</label><br/><input type="text" name="codes" id="codes" size="60"/><!-- ex: BIRE21MSG,optbire2mm521,optbire2m10e21,BIRE21MTC --><br/>
		<label for="semaines">Semaines désirées (sépars par virgules) :</label><br/><input type="text" name="semaines" id="semaines" value="<?php echo $semaines; ?>" size="60"/><br/>
		NOTE: ajd=S<?php echo date("W")+14; ?> et -->04/07/2010=S40<br/>
		Voulez vous le code du cours ou l'intitulé ?
<input type="radio" name="frites" value="oui" id="oui" checked="checked" /> <label for="oui">Code</label>
<input type="radio" name="frites" value="non" id="non" /> <label for="non">Intitulé</label><br/>

		
		<input type="submit" value="Lancer" />
	</p>
</form>

<?php
//----------------------------------------------------------------------
//                             Main
//----------------------------------------------------------------------

            
			
			
			
		
			
if (isset($_POST['codes']) && $_POST['codes']!='')
{
// PARAMETRES -------------------------------------------------------------------------------------------------------------
$codes = $_POST['codes'];
$semaines = $_POST['semaines'];

$projectID = 17; 
 	$projectID=0;		
if(isset($_POST['projectId'] )){

 $projectID = $_POST['projectId'];}

 echo('Vous avez choisis le projet : '.$projectID);	
// pour l'avoir facilement aller sur ADE au moment 
// de choisir le projet aller voir le code source
// -----------------------------------------------------------------------------------------------------------------------------

// CREATION DU COOKIE
//$id= rand(0,10000);
$fh = fopen("cookie_".$id.".txt","w");
fclose($fh);

// OUVERTURE DE SESSION
$ch1 = curl_init();
curl_setopt($ch1, CURLOPT_HEADER, 0);
curl_setopt($ch1, CURLOPT_COOKIEJAR, realpath("cookie_".$id.".txt"));
curl_setopt($ch1, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch1, CURLOPT_USERAGENT, 'Mozilla 5/0'); // utf-8
curl_setopt($ch1, CURLOPT_URL, $url.'/ade/custom/modules/plannings/direct_planning.jsp?weeks='.$semaines.'&code='.$codes.'&login=etudiant&password=student&projectId='.$projectID);

$ploupi = curl_exec($ch1);

curl_close($ch1);

// CHARGEMENT DE LA SESSION ET AFFICHAGE EN TABLEAU
$ch2 = curl_init();
curl_setopt($ch2, CURLOPT_HEADER, 0);
curl_setopt($ch2, CURLOPT_COOKIEFILE, realpath("cookie_".$id.".txt"));
curl_setopt($ch2, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch2, CURLOPT_USERAGENT, 'Mozilla 5/0'); // utf-8
curl_setopt($ch2, CURLOPT_URL, $url.'/ade/custom/modules/plannings/info.jsp?order=slot');
$horaire = curl_exec($ch2);
//echo('hepla <br/>'.$horaire.'<br/>');
curl_close($ch2);


// TRAITEMENT DE L'HORAIRE
$horaire = str_replace('<BODY>','',$horaire);
$horaire = str_replace('&amp;','&',$horaire);
$horaire = str_replace('&','&amp;',$horaire);

$dom = new DOMDocument(); // creation d'un objet DOM pour lire le html
 
$dom->loadHTML($horaire) or die('erreur');

$lignes = $dom->getElementsByTagName('tr'); // on recupere toute les lignes
//echo($horaire);


// CREATION DU FORMAT ICS
$buf_ics = "BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//ETSIL 3//iCal 1.0//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VTIMEZONE
TZID:Bruxelles\, Copenhague\, Madrid\, Paris
BEGIN:STANDARD
DTSTART:20001029T030000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
TZNAME:Paris\, Madrid
TZOFFSETFROM:+0200
TZOFFSETTO:+0100
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:20000326T020000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
TZNAME:Paris\, Madrid (heure d'été)
TZOFFSETFROM:+0100
TZOFFSETTO:+0200
END:DAYLIGHT
END:VTIMEZONE\n";

// EXTRACTION DES DONNEES DU DOMDOCUMENT
$stamp_id = rand(10,59);
$i=0;



// RECUPERATION DES LIENS DES COURS
$links = $dom->getElementsByTagName('a');

$liens = array();
for ($a = 0; $a < $links->length; $a++)
{
    if ($links->item($a)->hasAttribute('href'))
    {
	    $temp = $links->item($a)->getAttribute('href');
	  if(!preg_match('#^info.jsp#',$temp))
        $liens[] = $temp;
    }
}

// Celon le formulaire decider si on a besoins ou non des intitulé 
// pour limiter le temps d'execution (1 connection en plus par cours)
// On ignore totalement la recherche d'info si couché oui
	$needtheintitul = false;
	if (isset($_POST['frites']) && $_POST['frites']=='non'){
	  
	     $needtheintitul = true;}
	 
	if($needtheintitul){
	 echo('pas d\'intit');

//On fabrique l'url ou rechercher les info précises (vient du javascript ):) 
// et On vas rechercher les intituléunparun tache fastidieuse hélas :(
	$intitule = array();
	foreach ( $liens as $toto){
		$toto= preg_replace('#javascript:ev\((\d+)\)$#','eventInfo.jsp?eventId=$1&amp;noMenu=true',$toto);
		$intitule[] = getNameFromURLCODE($url.'/ade/custom/modules/plannings/',$toto,$id);
	}}


// SUPRESSION DU COOKIE
unlink(realpath("cookie_".$id.".txt"));

$aaa=-2; // 2 premieres lignes sont dles titres

foreach ($lignes as $ligne)
{  


	if($i>1)
	{
	   
		// les deux premiers tr sont des titres, osef
		$content = $ligne->childNodes;
		$noms = array('date','mat','sem','jour','heure','duree','etudiant','prof','salle');
		$entree = array();
		for($i=0;$i<=8;$i++)
		{
			$entree[$noms[$i]] = $content->item($i)->nodeValue; // attribution des valeurs aux variables

		}
		
		if($needtheintitul){
		//echo($aaa);
		  // $temptest = $entree[$noms[1]];
		  $entree[$noms[1]] = $intitule[$aaa];
		 // echo($temptest.' :  '.$entree[$noms[1]].'<br/>');
		}
		
		//echo('rototo  '.$entree['mat']);
		
		$heuress = CatHeure($entree['heure']); // tableau avec heure en 0 et minute en 1
		$hfin = HFin($heuress,$entree['duree']); // hhmmss
		$date = CutDate($entree['date']); // aaaammjj
		$salle = $entree['salle'];
		$cours='';
		$buf_ics .= "BEGIN:VEVENT\n";
		$description = $entree['mat']." - Salle : ".$salle." - Enseignant : ".$entree['prof']."\n";
		$buf_ics .= "DESCRIPTION:".$description;
		$buf_ics .= "DTSTAMP:20100130T1200".$stamp_id."Z\n";
		$buf_ics .= 'DTSTART;TZID="Bruxelles, Copenhague, Madrid, Paris":'.$date.'T'.$heuress[0].$heuress[1]."00\n";
		$buf_ics .= 'DTEND;TZID="Bruxelles, Copenhague, Madrid, Paris":'.$date.'T'.$hfin."\n";
		$buf_ics .= 'LOCATION:'.$salle."\n";
		$buf_ics .= "SUMMARY:".$entree['mat']." ".$cours."\nEND:VEVENT\n";	
	}
	$i++;
$aaa++;
	};
$buf_ics .= "END:VCALENDAR";



// CREATION DU FICHIER.ICS ET LIEN POUR TELECHARGER
$link = getFile('ics',$buf_ics);
echo '<h3>Télécharger le fichier</h3><a href="'.$link.'">'.ltrim($link,'ics/').'</a>';
}
