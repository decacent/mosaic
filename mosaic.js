angular
    .module('mosaicApp', ['ngMaterial'])
    .config(function($mdThemingProvider, $mdIconProvider){
            // $mdThemingProvider.theme('default')
            //     .primaryPalette('brown')
            //     .accentPalette('red');

    })
    .controller('AppCtrl', function ($scope, $timeout, $mdSidenav, $mdUtil, $log) {
      $scope.baseURL = "https://pages.nist.gov/mosaic/"
      // $scope.baseURL = "file:///Users/arvind/Research/Experiments/AnalysisTools/mosaic/_nistpages"
      $scope.docURL = $scope.baseURL+"/html/index.html"
      $scope.mailingListURL = $scope.baseURL+"/html/doc/mailingList.html"
      $scope.scriptURL = $scope.baseURL+"/html/doc/ScriptingandAdvancedFeatures.html"
      $scope.algoURL = $scope.baseURL+"/html/doc/Algorithms.html"
      $scope.exampleURL = $scope.baseURL+"/html/doc/examples.html"
      $scope.extendURL = $scope.baseURL+"/html/doc/Extend.html"
      $scope.addonURL = $scope.baseURL+"/html/doc/Addons.html"
      $scope.guiURL = $scope.baseURL+"/html/doc/WebInterface.html"
      $scope.developersURL = $scope.baseURL+"/html/doc/Developers.html"
      $scope.termsURL = $scope.baseURL+"/html/doc/Disclaimer.html"
      $scope.contactURL = "https://www.nist.gov/people/arvind-balijepalli"

      $scope.toggleLeft = buildToggler('left');
      $scope.toggleRight = buildToggler('right');

      $scope.useCaseIMG = generateUseCaseIMG();
      $scope.GUIIMG = generateGUIIMG();
      /**
       * Build handler to open/close a SideNav; when animation finishes
       * report completion in console
       */
      function generateGUIIMG() {
        var imgs = Array(
          "assets/img/GUI-01.png", 
          "assets/img/GUI-02.png",
          "assets/img/GUI-03.png",
          "assets/img/GUI-04.png"
          );
        var img = imgs[Math.floor(Math.random()*imgs.length)];

        return img 
      }
      function generateUseCaseIMG() {
        var imgs = Array("assets/img/UseCase-01.png", "assets/img/UseCase-02.png");
        var img = imgs[Math.floor(Math.random()*imgs.length)];

        return img 
      }

      function buildToggler(navID) {
        var debounceFn =  $mdUtil.debounce(function(){
              $mdSidenav(navID)
                .toggle()
                .then(function () {
                  $log.debug("toggle " + navID + " is done");
                });
            },300);
        return debounceFn;
      }
    })
    .controller('LeftCtrl', function ($scope, $timeout, $mdSidenav, $log) {
      $scope.close = function () {
        $mdSidenav('left').close()
      };
    });